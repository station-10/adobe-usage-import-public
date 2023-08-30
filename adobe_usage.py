"""
This script provides a class, AdobeAPI, for:

- Connecting to the Adobe Analytics APIs using server-to-server OAuth authentication
- Fetching paginated data from any Adobe API endpoint
- Downloading Adobe Analytics usage and admin logs within a given date range
- Enriching the usage and admin logs by spliting out various fields
- Validating the enriched file before importing it into Adobe Analytics
- Importing the enriched usage and admin logs to Adobe Analytics

Relevant API documentation:
- Original Adobe blog on usage data in Adobe Analytics: https://express.adobe.com/page/hnYfQPThMu2dr/
- Usage and Admin Logs: https://developer.adobe.com/analytics-apis/docs/2.0/guides/endpoints/usage/
- Bulk Data Insertion: https://developer.adobe.com/analytics-apis/docs/2.0/guides/endpoints/bulk-data-insertion/
"""


import csv
from datetime import datetime, timedelta
import json
import re
import gzip
import os
import shutil
import requests
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import pandas as pd


class ConnectionFailure(Exception):
    """Raised when there is a failure in connecting to the API."""


class RequestFailure(Exception):
    """Raised when there is a failure in making a request to the API."""


class ExistingDataError(Exception):
    """Exception raised when there is existing data in the report suite for the given date range."""


class AdobeAPI:
    """
    A class to interact with the Adobe API using server-to-server OAuth for authentication.

    Usage example:
        adobe_api = AdobeAPI('config.json')
    """

    def __init__(self, config_path="config.json", timeout=10):
        self.config = self._load_config(config_path)
        self.timeout = timeout
        self.access_token = None
        self.company_id = self.config["company_id"]
        self.session = requests.Session()
        self._connect()

    def _load_config(self, config_path):
        """Load the configuration file."""
        with open(config_path, "r", encoding="utf-8") as config_file:
            return json.load(config_file)

    def _connect(self):
        """
        Connect to the Adobe API using OAuth for authentication.

        :raises: ConnectionFailure if there's an error making the request
        """
        url = f"https://ims-na1.adobelogin.com/ims/token/v3?client_id={self.config['client_id']}"

        request_payload = {
            "client_secret": self.config["client_secret"],
            "grant_type": "client_credentials",
            "scope": self.config["scopes"],
        }

        response = self.session.post(
            url,
            data=request_payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=self.timeout,
        )

        if response.status_code == 200:
            self.access_token = response.json()["access_token"]
            self.session.headers.update(
                {
                    "Authorization": f"Bearer {self.access_token}",
                    "x-api-key": self.config["client_id"],
                }
            )
        else:
            raise ConnectionFailure(
                f"Request failed with status code: {response.status_code}"
                f"\nResponse text: {response.text}"
            )

    def refresh_access_token(self):
        """Refresh the access token."""
        self._connect()

    def inclusive_date_range(self, start_date, end_date):
        """
        Convert start_date and end_date strings to datetime objects
        that are inclusive of the end date.

        :param start_date: The start date in the format YYYY-MM-DD
        :param end_date: The end date in the format YYYY-MM-DD
        :return: A tuple of the start date and end date as datetime objects
        """
        # Parse start_date and end_date strings as datetime objects
        start_date_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_date_dt = datetime.strptime(end_date, "%Y-%m-%d")

        # Raise ValueError if start_date is after end_date
        if start_date_dt > end_date_dt:
            raise ValueError("Start date must be before or equal to end date")

        # Adjust end_date to be inclusive: add one day and subtract one second
        end_date_dt += timedelta(days=1, seconds=-1)

        return start_date_dt, end_date_dt

    def get_usage_audit_logs(
        # pylint: disable=invalid-name
        self,
        company_id,
        start_date,
        end_date,
        login=None,
        ip=None,
        rsid=None,
        event_type=None,
        event=None,
        limit=1000,
    ):
        """
        Get usage audit logs.

        :param company_id: The company ID
        :param start_date: The start date (YYYY-MM-DD)
        :param end_date: The end date (YYYY-MM-DD)
        :param login: The login name
        :param ip: The IP address
        :param rsid: The report suite ID
        :param event_type: The event type
        :param event: The event
        :param limit: The number of items to fetch per page
        :return: A list of usage audit logs
        """
        all_data = []

        start_date_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_date_dt = datetime.strptime(end_date, "%Y-%m-%d")

        print(f"Fetching usage audit logs for {start_date} to {end_date}...")

        while start_date_dt <= end_date_dt:
            current_start_date = start_date_dt
            current_end_date = min(current_start_date + timedelta(days=89), end_date_dt)

            # Get inclusive date range datetime objects
            current_start_date, current_end_date = self.inclusive_date_range(
                current_start_date.strftime("%Y-%m-%d"),
                current_end_date.strftime("%Y-%m-%d"),
            )

            # Convert datetime objects to ISO formatted strings for API request
            start_date_str = current_start_date.strftime("%Y-%m-%dT%H:%M:%S")
            end_date_str = current_end_date.strftime("%Y-%m-%dT%H:%M:%S")

            page = 0
            has_more_pages = True

            print(f"Fetching data chunk for {start_date_str} to {end_date_str}...")

            while has_more_pages:
                url = f"https://analytics.adobe.io/api/{company_id}/auditlogs/usage"

                params = {
                    "startDate": start_date_str,
                    "endDate": end_date_str,
                    "limit": limit,
                    "page": page,
                }

                optional_params = {
                    "login": login,
                    "ip": ip,
                    "rsid": rsid,
                    "eventType": event_type,
                    "event": event,
                }

                for key, value in optional_params.items():
                    if value:
                        params[key] = value

                response = self.session.get(url, params=params, timeout=self.timeout)

                if response.status_code == 200:
                    data_page = response.json()
                    all_data.extend(data_page["content"])
                    has_more_pages = not data_page["lastPage"]
                    print(f"Fetched page {page+1} of {data_page['totalPages']}")
                else:
                    raise RequestFailure(
                        f"Request failed with status code: {response.status_code}"
                        f"\nResponse text: {response.text}"
                    )

                page += 1

            start_date_dt = current_end_date + timedelta(days=1)

        print(
            f"Fetching usage audit logs finished. Fetched {len(all_data)} rows of data"
        )
        return all_data

    def update_event_types(self, json_file_path):
        """
        Update the event types in the JSON file.
        Converts them from a number to a useful description.

        :param json_file_path: The path to the JSON file
        """
        # event lookup table
        event_types_dict = {
            0: "No Category",
            1: "Login failed",
            2: "Login successful",
            3: "Admin Action",
            4: "Security setting change",
            5: "Report viewed",
            6: "Report downloaded",
            7: "Alert sent",
            8: "User Action",
            9: "Tool viewed",
            10: "Adobe Action",
            11: "Password Recovery",
            12: "BookMarks",
            13: "Dashboards",
            14: "Alerts",
            15: "Calendar Events",
            16: "Targets",
            17: "Report Settings",
            18: "Scheduled Reports",
            19: "Exclude By IP",
            20: "Name Pages",
            21: "Classifications",
            22: "Data Sources",
            23: "Workspace Project",
            24: "Segment",
            25: "Calculated Metric",
            26: "Date Range",
            27: "Virtual Report Suite",
            28: "Contribution Analysis",
            30: "Excel Data Block Request",
            31: "Excel Login Failure",
            32: "Excel Login Success",
            41: "Mobile Login Failure",
            42: "Mobile Login Success",
            61: "Api Method",
        }

        with open(json_file_path, "r", encoding="utf-8") as json_file:
            json_data = json.load(json_file)

        for i, event in enumerate(json_data):
            try:
                event_type = event.get("eventType")
                if event_type is None:
                    event["eventType"] = "Unknown Event Type"
                else:
                    event_type_int = (
                        int(event_type) if isinstance(event_type, (str, int)) else None
                    )
                    if event_type_int in event_types_dict:
                        event["eventType"] = event_types_dict[event_type_int]
                    else:
                        event["eventType"] = "Unknown Event Type: " + str(
                            event_type_int
                        )
            except KeyError as error:
                print(f"Error processing event {i}: {event}")
                print(f"Error message: {error}")
                print()
            except ValueError as error:
                print(f"Error processing event {i}: {event}")
                print(f"Error message: {error}")
                print()

        # write the updated JSON file
        with open(json_file_path, "w", encoding="utf-8") as json_file:
            json.dump(json_data, json_file, indent=4)
            print(f"update_event_types function updated JSON file: {json_file_path}")

    def add_component_info(self, json_file_path):
        """
        Add component info to the JSON file.
        The component name, ID and owner are extracted from the eventDescription field based on a regex pattern.

        :param json_file_path: The path to the JSON file
        """
        # regex pattern for component info
        pattern = r"Name=(?P<name>.*?)\sId=(?P<id>\S+)(?:\sOwner=(?P<owner>.*))?"

        # Read the JSON data from the file
        with open(json_file_path, "r", encoding="utf-8") as json_file:
            json_data = json.load(json_file)

        updated_data = []
        regex = re.compile(pattern)

        # Loop through each entry in the JSON data
        for item in json_data:
            event_description = item.get("eventDescription", "")

            match = regex.search(event_description)
            if match:
                item["componentName"] = match.group("name").strip()
                item["componentId"] = match.group("id").strip()
                item["componentOwner"] = (
                    match.group("owner").strip()
                    if "owner" in match.groupdict() and match.group("owner")
                    else "N/A"
                )

            updated_data.append(item)

        # Write the updated JSON data to the file
        with open(json_file_path, "w", encoding="utf-8") as json_file:
            json.dump(updated_data, json_file, indent=4)
            print(f"add_component_info function updated JSON file: {json_file_path}")

    def add_adobe_events(self, json_file_path):
        """
        Add Adobe events to the JSON file, for use in s.events.

        :param json_file_path: The path to the JSON file
        """

        event_name_dict = {
            "event1": "project created",
            "event2": "project viewed",
            "event3": "project updated",
            "event4": "project deleted",
            "event5": "sharing project",
            "event6": "segment created",
            "event7": "segment updated",
            "event8": "segment deleted",
            "event9": "sharing segment",
            "event10": "calculated metric created",
            "event11": "calculated metric updated",
            "event12": "calculated metric deleted",
            "event13": "sharing calculated metric",
            "event14": "date range created",
            "event15": "date range updated",
            "event16": "date range deleted",
            "event17": "sharing date range",
            "event18": "virtual report suite created",
            "event19": "virtual report suite updated",
            "event20": "virtual report suite deleted",
            "event21": "alert created",
            "event22": "alert updated",
            "event23": "alert deleted",
            "event24": "sharing alert",
            "event25": "delivered alert",
            "event26": "classification",
            "event27": "viewed permissions",
            "event28": "viewed company",
            "event29": "viewed logs",
            "event30": "successful login",
            "event31": "login failed",
            "event32": "api operation",
        }

        # run through the JSON file and add a new event field based on the event_name_dict
        with open(json_file_path, "r", encoding="utf-8") as json_file:
            json_data = json.load(json_file)

        # Loop through each entry in the JSON data
        for entry in json_data:
            # Set a default value for the "event" field
            entry["event"] = ""
            event_description = entry["eventDescription"].lower()

            # Check if any event keyword from the dictionary is present in the eventDescription
            for event_key, event_value in event_name_dict.items():
                if event_value.lower() in event_description:
                    entry["event"] = event_key
                    break

        # write the updated JSON file
        with open(json_file_path, "w", encoding="utf-8") as json_file:
            json.dump(json_data, json_file, indent=4)
            print(f"add_adobe_events function updated JSON file: {json_file_path}")

    def write_to_csv_for_bulk_import(self, json_file_path, csv_file_path, rsid):
        """
        Write the JSON data to a CSV file in the correct format for the Bulk Data Import API.

        :param json_file_path: The path to the JSON file
        :param csv_file_path: The path to the CSV file
        :param usage_rsid: The usage report suite ID
        """
        report_suite_id = rsid

        with open(json_file_path, "r", encoding="utf-8") as json_file, open(
            csv_file_path, "w", newline="", encoding="utf-8"
        ) as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(
                [
                    "reportSuiteID",
                    "Timestamp",
                    "marketingCloudVisitorID",
                    "pageName",
                    "userAgent",
                    "eVar1",
                    "eVar2",
                    "eVar3",
                    "eVar4",
                    "eVar5",
                    "eVar6",
                    "eVar7",
                    "events",
                ]
            )

            for log in json.load(json_file):
                event_desc_full = f"{log['eventType']};{log['eventDescription']}"

                # Set timestamp to the dateCreated field, converted to unix timestamp
                timestamp = int(datetime.fromisoformat(log["dateCreated"]).timestamp())

                # if login is not null, set marketingCloudVisitorID to the login field, without the @domain
                # otherwise, set marketingCloudVisitorID to "unknown"
                if log["login"] is None:
                    marketing_cloud_visitor_id = "unknown"
                else:
                    login = log["login"].split("@")[0]
                    marketing_cloud_visitor_id = login

                # Set s.pagename to the event_desc field
                s_pagename = event_desc_full

                # Set evars
                evar_1 = login
                evar_2 = event_desc_full
                evar_3 = log["eventType"]
                evar_4 = log["eventDescription"]
                # using log.get() to avoid KeyError if the key is not present
                evar_5 = log.get("componentId", "")
                evar_6 = log.get("componentName", "")
                evar_7 = log.get("componentOwner", "")

                # set events to the event field
                events = log["event"]

                # Write values to CSV row
                csv_writer.writerow(
                    [
                        report_suite_id,
                        timestamp,
                        marketing_cloud_visitor_id,
                        s_pagename,
                        "filler_user_agent",
                        evar_1,
                        evar_2,
                        evar_3,
                        evar_4,
                        evar_5,
                        evar_6,
                        evar_7,
                        events,
                    ]
                )

        print(f"Data written to {csv_file_path}")

    def data_sense_check(self, csv_file_path):
        """
        Perform a data sense check on the CSV file.

        :param csv_file_path: The path to the CSV file
        """
        # Read the CSV file
        data = pd.read_csv(csv_file_path)

        # Convert the timestamp to datetime format
        data["Datetime"] = pd.to_datetime(data["Timestamp"], unit="s")

        # Calculate the maximum and minimum dates
        min_date = data["Datetime"].min()
        max_date = data["Datetime"].max()
        print(f"Minimum Datetime from data_sense_check: {min_date}")
        print(f"Maximum Datetime from data_sense_check: {max_date}")

        # Count the occurrences of each date
        date_counts = data["Datetime"].dt.date.value_counts().sort_index()

        # Create a bar chart of rows over time with one bar per day
        plt.figure(figsize=(10, 5))
        axis = date_counts.plot(kind="bar")
        plt.title("Rows Over Time")
        plt.xlabel("Date")
        plt.ylabel("Row Count")
        plt.xticks(rotation=90)  # Angle x-axis labels to 90 degrees

        # Set the maximum number of x-axis ticks
        axis.xaxis.set_major_locator(MaxNLocator(integer=True, prune="both", nbins=20))

        plt.show()

    def gzip_file(self, file_path):
        """
        Gzip a file.

        :param file_path: The path to the file to gzip
        :return: The path to the gzipped file
        """
        gzip_file_path = file_path + ".gz"

        with open(file_path, "rb") as src_file, gzip.open(
            gzip_file_path, "wb"
        ) as dest_file:
            shutil.copyfileobj(src_file, dest_file)

        return gzip_file_path

    def validate_csv(self, csv_file_path):
        """
        Validate a CSV file using Adobe's validation endpoint.

        :param csv_file_path: The path to the CSV file to be validated
        :return: The response from the validation endpoint
        :raises: RequestFailure if there's an error making the request
        """
        url = "https://analytics-collection.adobe.io/aa/collect/v1/events/validate"

        # Add additional headers for this specific request
        additional_headers = {
            "accept": "application/json",
            "x-adobe-vgid": "usage_group1",
        }
        self.session.headers.update(additional_headers)

        # Gzip the file
        gzip_file_path = self.gzip_file(csv_file_path)

        # Make the request
        with open(gzip_file_path, "rb") as file:
            files = {"file": file}
            response = self.session.post(url, files=files, timeout=self.timeout)

        # Clean up the gzipped file
        os.remove(gzip_file_path)

        # Remove the additional headers after the request is complete
        for header in additional_headers:
            self.session.headers.pop(header, None)

        if response.status_code == 200:
            validation_result = response.json()
            return validation_result
        else:
            raise RequestFailure(
                f"Request failed with status code: {response.status_code}"
                f"\nResponse text: {response.text}"
            )

    def extract_rsid_and_date_range(self, csv_file_path):
        """
        Extract the report suite ID and date range from a CSV file.
        For use in the is_there_existing_data_for_date_range function
        to check the report suite for existing data.

        :param csv_file_path: The path to the CSV file
        :return: The report suite ID and date range
        """
        with open(csv_file_path, "r", encoding="utf-8") as file:
            reader = csv.reader(file)
            next(reader)  # Skip the header row

            rsid = None
            min_date = None
            max_date = None

            # Get the rsid and check it is consistent across all rows
            for row in reader:
                if not rsid:
                    rsid = row[0]
                else:
                    if row[0] != rsid:
                        raise ValueError("Multiple report suite IDs found in the CSV")

                # Get the date range
                timestamp = int(row[1])
                date = datetime.utcfromtimestamp(timestamp).date()

                if min_date is None or date < min_date:
                    min_date = date
                if max_date is None or date > max_date:
                    max_date = date

            print(f"Report Suite ID extracted from csv: {rsid}")
            print(f"Minimum Date extracted from csv: {min_date}")
            print(f"Maximum Date extracted from csv: {max_date}")
            return rsid, min_date.strftime("%Y-%m-%d"), max_date.strftime("%Y-%m-%d")

    def is_there_existing_data_for_date_range(self, csv_file_path):
        """
        Request a report from the Adobe Analytics API.

        :param csv_file_path: The path to the CSV file
        :return: The response JSON object
        """
        # Extract the report suite ID and date range from the CSV file
        rsid, start_date, end_date = self.extract_rsid_and_date_range(csv_file_path)

        # Get the date range in the format required by the API
        start_date_dt, end_date_dt = self.inclusive_date_range(start_date, end_date)

        # Convert datetime objects to ISO formatted strings for API request
        start_date_str = start_date_dt.strftime("%Y-%m-%dT%H:%M:%S")
        end_date_str = end_date_dt.strftime("%Y-%m-%dT%H:%M:%S")

        url = f"https://analytics.adobe.io/api/{self.company_id}/reports"

        request_json = {
            "rsid": f"{rsid}",
            "globalFilters": [
                {"type": "dateRange", "dateRange": f"{start_date_str}/{end_date_str}"}
            ],
            "metricContainer": {
                "metrics": [
                    {
                        "columnId": "metrics/occurrences:::0",
                        "id": "metrics/occurrences",
                        "filters": ["STATIC_ROW_COMPONENT_1"],
                    }
                ],
                "metricFilters": [
                    {
                        "id": "STATIC_ROW_COMPONENT_1",
                        "type": "segment",
                        "segmentId": "All_Visits",
                    }
                ],
            },
            "settings": {
                "countRepeatInstances": True,
                "includeAnnotations": True,
                "dimensionSort": "asc",
            },
        }

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "x-proxy-global-company-id": self.company_id,
        }

        # Make the request
        response = self.session.post(
            url, json=request_json, headers=headers, timeout=self.timeout
        )

        if response.status_code == 200:
            response_json = response.json()
            print("Existing data check response:")
            print(response_json)

            if "summaryData" not in response_json:
                raise KeyError(
                    "The 'summaryData' key is not found in the response JSON"
                )

            summary_data = response_json["summaryData"]

            # Check if the 'totals' key is in the 'summaryData' dictionary
            if "totals" not in summary_data:
                raise KeyError(
                    "The 'totals' key is not found in the 'summaryData' dictionary"
                )

            # If there's existing data, the first element in the 'totals' list will be greater than 1
            # Occasionally we get 1 or 2 values outside of the date range of the request, so
            if summary_data["totals"][0] > 2:
                print(
                    "There IS significant existing data for this date range. Summary Data Total:",
                    summary_data["totals"][0],
                )
                return True
            else:
                print(
                    "There IS NOT significant existing data for this date range. Summary Data Total:",
                    summary_data["totals"][0],
                )
                return False
        else:
            raise RequestFailure(
                f"Request failed with status code: {response.status_code}"
                f"\nResponse text: {response.text}"
            )

    def bulk_data_insertion(self, csv_file_path):
        """
        Send a CSV file to the bulk data insertion endpoint. This function
        includes checks to ensure that the CSV file is valid and that there
        is no existing data for the date range.

        :param csv_file_path: The path to the CSV file to be sent
        :return: The response from the ingestion endpoint
        :raises: RequestFailure if there's an error making the request
        """
        # Validate the CSV file
        validation_result = self.validate_csv(csv_file_path)
        if not validation_result["success"]:
            raise RequestFailure("CSV file validation failed")

        # Check if there's existing data for the date range
        has_existing_data = self.is_there_existing_data_for_date_range(csv_file_path)
        if has_existing_data:
            raise ExistingDataError(
                "There is existing data for this date range. Bulk data insertion will not proceed."
            )

        print(
            "There is no existing data for this date range. Bulk data insertion will proceed."
        )

        # If neither of the above exceptions are raised, proceed with the bulk data insertion
        url = "https://analytics-collection.adobe.io/aa/collect/v1/events"

        # Add the additional headers required by the ingestion endpoint
        additional_headers = {
            "accept": "application/json",
            "x-adobe-vgid": "usage_group1",
        }
        self.session.headers.update(additional_headers)

        # Gzip the CSV file
        gzip_file_path = self.gzip_file(csv_file_path)

        # Send the gzipped file to the ingestion endpoint
        with open(gzip_file_path, "rb") as file:
            files = {"file": file}
            response = self.session.post(url, files=files, timeout=self.timeout)

        # Clean up the gzipped file
        os.remove(gzip_file_path)

        # Remove the additional headers after the request is complete
        for header in additional_headers:
            self.session.headers.pop(header, None)

        if response.status_code == 200:
            ingestion_result = response.json()
            return ingestion_result
        else:
            raise RequestFailure(
                f"Request failed with status code: {response.status_code}"
                f"\nResponse text: {response.text}"
            )


####################################################################################################
# Usage example
####################################################################################################

if __name__ == "__main__":
    # Create an instance of the AdobeAPI class
    adobe_api = AdobeAPI("config.json")

    # fetch all usage audit logs for a date range
    all_usage_audit_logs = adobe_api.get_usage_audit_logs(
        adobe_api.company_id,
        start_date="2022-02-01",
        end_date="2022-02-28",  # inclusive
    )

    # Write the output to a local file
    with open("all_usage_audit_logs.json", "w", encoding="utf-8") as f:
        json.dump(all_usage_audit_logs, f, indent=4)

    # update event types
    adobe_api.update_event_types("all_usage_audit_logs.json")

    # add Adobe events
    adobe_api.add_adobe_events("all_usage_audit_logs.json")

    # add component information
    adobe_api.add_component_info("all_usage_audit_logs.json")

    # Write out to CSV for bulk import
    adobe_api.write_to_csv_for_bulk_import(
        "all_usage_audit_logs.json",
        "all_usage_audit_logs.csv",
        rsid="your-rsid-goes-here",
    )

    # Sense check the data
    adobe_api.data_sense_check("all_usage_audit_logs.csv")

    # # Check for existing data
    # adobe_api.is_there_existing_data_for_date_range("all_usage_audit_logs.csv")

    # Validate CSV using Adobe's bulk validation endpoint
    adobe_api.validate_csv("all_usage_audit_logs.csv")

    # # DO NOT RUN THIS UNLESS YOU ARE SURE YOU WANT TO PERFORM A BULK DATA INSERTION
    # # Perform the data insertion
    # adobe_api.bulk_data_insertion("all_usage_audit_logs.csv")
