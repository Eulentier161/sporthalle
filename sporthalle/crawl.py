import os
import sys
import re
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta

import caldav
import httpx
from bs4 import BeautifulSoup, PageElement
from dotenv import load_dotenv

from .utils import parse_datetime, add_hours_avoiding_next_day

load_dotenv()

logging.basicConfig(level=logging.INFO)


class CalendarEvent:
    def __init__(
        self,
        category: str,
        artist: str,
        day: date,
        doors: datetime | None,
        begin: datetime | None,
        description: str,
    ):
        self.category = category
        self.artist = artist
        self.day = day
        self.doors = doors
        self.begin = begin
        self.description = description

    @property
    def doors_human(self) -> str:
        return self.doors.strftime('%H:%M') if self.doors else "??:??" + " Uhr"
    
    @property
    def begin_human(self) -> str:
        return self.begin.strftime('%H:%M') if self.begin else "??:??" + " Uhr"
    
    @property
    def day_human(self) -> str:
        return self.day.strftime('%d.%m.%Y')

    def __repr__(self) -> str:
        return f"[{self.category}] {self.artist} am {self.day_human} um {self.begin_human} (Einlass ab {self.doors_human})"


def fetch_webpage_content(url: str) -> BeautifulSoup:
    res = httpx.get(url)
    return BeautifulSoup(res.content.decode("ISO-8859-1"), "html.parser")


def find_elements(soup: BeautifulSoup) -> tuple[list[PageElement], list[PageElement]]:
    start_elements = soup.find_all(class_="rahmen_radius_l")
    end_elements = soup.find_all(style="margin-left:4px;margin-top:4px;font-size:8pt;margin-bottom:-8px")
    return start_elements, end_elements


def collect_selected_elements(
    start_elements: list[PageElement], end_elements: list[PageElement]
) -> list[list[PageElement]]:
    all_selected_elements = []
    for start_element in start_elements:
        selected_elements = []
        current_element = start_element
        while current_element and current_element not in end_elements:
            selected_elements.append(current_element)
            current_element = current_element.find_next_sibling()
        if current_element in end_elements:
            selected_elements.append(current_element)
        all_selected_elements.append(selected_elements)
    return all_selected_elements


def parse_event(group: list[PageElement]) -> CalendarEvent | None:
    artist = group[0].text.strip()
    day_date_type = group[1].text.strip()
    category = day_date_type.split(" ")[-1]
    date_string = map(int, day_date_type.split(" ")[1].split("."))
    d = date(*reversed(list(date_string)))
    description = "".join(x.text.strip() for x in group[2:])
    doors_match = re.search(r"Einlass: (\d{2}:\d{2}) Uhr", description)
    begin_match = re.search(r"Beginn: (\d{2}:\d{2}) Uhr", description)
    doors = parse_datetime(d, doors_match)
    begin = parse_datetime(d, begin_match)

    if not doors and not begin:
        logging.info(f"Force event: {artist} on {d} forced to open doors at 16:00 due to missing data.")
        doors = datetime.combine(d, time(hour=16))

    return CalendarEvent(category, artist, d, doors, begin, description)


def crawl() -> list[CalendarEvent]:
    soup = fetch_webpage_content("https://termine.sporthallehamburg.de/pr/clipper.php")
    start_elements, end_elements = find_elements(soup)
    if not start_elements or not end_elements:
        return []
    all_selected_elements = collect_selected_elements(start_elements, end_elements)
    events = [parse_event(group) for group in all_selected_elements]
    return [event for event in events if event is not None]


def delete_all_events(calendar: caldav.Calendar):
    for event in calendar.events():
        logging.info(f"Deleting event: {event.instance.vevent.summary.value}")
        event.delete()


def find_existing_event(calendar: caldav.Calendar, event: CalendarEvent) -> caldav.Event | None:
    for existing_event in calendar.events():
        existing_event_data = existing_event.instance.vevent
        if (
            existing_event_data.summary.value == f"[{event.category}] {event.artist}"
            and existing_event_data.dtstart.value.date() == event.day
        ):
            return existing_event
    return None


def update_or_create_event(calendar: caldav.Calendar, event: CalendarEvent):
    existing_event = find_existing_event(calendar, event)
    dtstart = event.doors if event.doors else event.begin
    dtend = add_hours_avoiding_next_day(event.begin, 4) if event.begin else add_hours_avoiding_next_day(event.doors, 6)
    summary = f"[{event.category}] {event.artist}"

    if existing_event:
        existing_event_data = existing_event.instance.vevent
        if (
            existing_event_data.dtstart.value != dtstart
            or existing_event_data.dtend.value != dtend
            or existing_event_data.summary.value != summary
        ):
            existing_event_data.dtstart.value = dtstart
            existing_event_data.dtend.value = dtend
            existing_event_data.summary.value = summary
            existing_event.save()
            logging.info(f"Updated event: {summary}")
        else:
            logging.info(f"No changes for event: {summary}")
    else:
        calendar.save_event(
            dtstart=dtstart,
            dtend=dtend,
            summary=summary,
        )
        logging.info(f"Created event: {summary}")


def sync_events(calendar: caldav.Calendar, new_events: list[CalendarEvent]):
    existing_events = calendar.events()
    new_event_summaries = {f"[{event.category}] {event.artist}" for event in new_events}

    # Function to update or create an event
    def update_or_create(event):
        update_or_create_event(calendar, event)

    # Function to delete an event
    def delete_event(existing_event):
        existing_event_data = existing_event.instance.vevent
        if existing_event_data.summary.value not in new_event_summaries:
            logging.info(f"Deleting event: {existing_event_data.summary.value}")
            existing_event.delete()

    # Update or create events in parallel
    with ThreadPoolExecutor(max_workers=10) as executor:
        executor.map(update_or_create, new_events)

    # Delete events not in the new events list in parallel
    with ThreadPoolExecutor(max_workers=10) as executor:
        executor.map(delete_event, existing_events)


def main():
    client = caldav.DAVClient(
        url=os.getenv("CALENDAR_URL"),
        username=os.getenv("NEXTCLOUD_USERNAME"),
        password=os.getenv("NEXTCLOUD_PASSWORD"),
    )
    principal = client.principal()
    calendars = principal.calendars()
    calendar = calendars[0]

    # Delete all events
    if "--delete" in sys.argv:
        return delete_all_events(calendar)

    events = crawl()
    sync_events(calendar, events)


if __name__ == "__main__":
    main()
