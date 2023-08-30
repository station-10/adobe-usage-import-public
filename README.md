# adobe-usage-import

This is a Python script for the Adobe Analytics API, which allows you to:

- Connect to the Adobe Analytics APIs using server-to-server OAuth authentication
- Download Adobe Analytics usage and admin logs within a given date range
- Enrich the usage and admin logs by splitting out various fields and adding user friendly event names
- Validate the file before importing it into Adobe Analytics
- Import the enriched usage and admin logs to Adobe Analytics

## Installation

1. Clone this repository or download the source code.
2. Install the required libraries by running `pip install -r requirements.txt` in the root directory of the project.

## Usage

### Authentication

This project connects to the Adobe APIs using Server-toServer OAuth authentication. See the [Adobe documentation](https://developer.adobe.com/developer-console/docs/guides/authentication/ServerToServerAuthentication/implementation/) for information on how to generate a private key and obtain your API credentials.

When that is done, you'll need to create a config.json file containing your Adobe Analytics API credentials:

```json
{
  "client_id": "YOUR_CLIENT_ID",
  "client_secret": "YOUR_CLIENT_SECRET",
  "company_id": "YOUR_COMPANY_ID",
  "scopes": "comma, separated, list, of, scopes"
}
```
NOTE: Company ID is not to be confused with AdobeOrg from your API configuration.  Company ID can be found from Adobe Analytics > Admin > All Admin > Company Settings > API Access.  Look for your `Global Company ID`

Then, you can use the AdobeAPI class to interact with the Adobe Analytics API. Here's an example of how to initialize the API wrapper:

```python
# Create an instance of the AdobeAPI class
adobe_api = AdobeAPI("config.json")
```

### Fetching data from the Adobe Analytics API

`get_usage_audit_logs`

```python
# fetch all usage audit logs for a date range
all_usage_audit_logs = adobe_api.get_usage_audit_logs(
    adobe_api.company_id,
    start_date="2022-02-01",
    end_date="2023-04-26",  # inclusive
)
```

This function retrieves usage audit logs from the Adobe Analytics API. It takes several parameters such as company_id, start_date, end_date, and other optional filters like login, ip, rsid, event_type, and event. The function returns a list of usage audit logs in JSON format.

The usage logs endpoint is paginated, so the function will automatically fetch all pages of data. It also only supports a maximum date range of 3 months, so if the request covers a longer date range, the function will handle splitting that into multiple requests and returning a single output JSON object.

The output should then be written to a local file, for example:

```python
# Write the output to a local file
with open("all_usage_audit_logs.json", "w", encoding="utf-8") as f:
    json.dump(all_usage_audit_logs, f, indent=4)
```

### Enriching the usage audit logs

`update_event_types`

```python
# update event types
adobe_api.update_event_types("all_usage_audit_logs.json")
```

This function updates the event types in the JSON file, from numbers to more descriptive labels. It then writes the updated JSON data back to the same file.

`add_component_info`

```python
# add component information
adobe_api.add_component_info("all_usage_audit_logs.json")
```

This function reads the JSON file and adds component name, ID, and owner to each entry in the JSON data. These are extracted from the the eventDescription field of each entry based on a regex pattern. It then writes the updated JSON data back to the same file.

`add_adobe_events`

```python
# add Adobe events
adobe_api.add_adobe_events("all_usage_audit_logs.json")
```

This function adds Adobe 'events' to the JSON file based on the event descriptions in the JSON data. These events populate the s.events field in the data insertion, giving you metrics in Adobe Analytics for various usage actions. Then it writes the updated JSON data back to the same file.

### Writing to csv for bulk import

`write_to_csv_for_bulk_import`

```python
# Write out to CSV for bulk import
adobe_api.write_to_csv_for_bulk_import(
    "all_usage_audit_logs.json",
    "all_usage_audit_logs.csv",
    rsid="your-rsid-goes-here",
)
```

This function writes the JSON data to a CSV file in the correct format for the Adobe Analytics Bulk Data Import API. It takes the paths to the JSON and CSV files, and your report suite id (see below for setting this up) as input parameters. The function reads the JSON data and extracts relevant fields, converting some of them into the required formats. It then writes the extracted data to a CSV file.

`data_sense_check`

```python
# Sense check the data
adobe_api.data_sense_check("all_usage_audit_logs.csv")
```

This function performs a data sense check on the CSV file. It reads the CSV file, calculates the minimum and maximum dates, displaying them in the console output. The function also counts the occurrences of each date and creates a bar chart that displays the number of rows over time, with one bar per day. This visualization helps in understanding the distribution of data over time.

### Creating the Adobe Analytics report suite

You will need to create a new report suite in Adobe Analytics to store this data. In future it would be good to automate this via the API but for now it has to be done manually.

> **Note**
> Be sure to check that the report suite is timestamp-enabled or timestamp optional, as per https://developer.adobe.com/analytics-apis/docs/2.0/guides/endpoints/bulk-data-insertion/#prerequisites

The report suite should contain the following eVars and events, which are used in the data insertion:

#### Events

```json
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
```

#### eVars

```json
"eVar1": "User Login",
"eVar2": "Event Name Full",
"eVar3": "Event Type",
"eVar4": "Event Description",
"eVar5": "Component ID",
"eVar6": "Component Name",
"eVar7": "Component Owner",
```

eVars should be set to 'hit' expiry rather than the default 'visit' expiry.

### Importing the usage audit logs to Adobe Analytics

`bulk_data_insertion`

```python
# Perform the data insertion
adobe_api.bulk_data_insertion("all_usage_audit_logs.csv")
```

This function sends the CSV file to the Adobe Analytics Bulk Data Insertion API endpoint.

Because removing data from Adobe Analytics is very difficult, it performs two checks before sending the data:

1. Validate the CSV file using the `validate_csv` function. If the validation fails, a RequestFailure exception is raised.
2. Check if there's existing data for the date range in the CSV file using the `is_there_existing_data_for_date_range` function. If there's existing data, an ExistingDataError exception is raised, and the bulk data insertion does not proceed.

If neither of the exceptions is raised, the function proceeds with the bulk data insertion. If the request is successful, it returns the ingestion result. If not, it raises a RequestFailure exception with the status code and response text.

> **Note**
> If you're inserting historic data, be aware it can take up to 24 hours for the data to appear in Adobe Analytics. Unlike data recieved for the current day, which appears in the reports within an hour. See here for more details: https://experienceleague.adobe.com/docs/analytics/technotes/latency.html#features-that-depend-on-latency

## Ideas for Future Improvements

- Remove the reliance on writing actual json and csv files out to disk, keep them in memory instead. Doing this while writing the script was helpful as it allowed easy debugging, but it makes automating the script in something like a Google Cloud Function difficult.
- Add a script to automate the creation of the report suite, since creating all those events and evars is a faff.

## Useful Links

This project relies heavily on the below documentation:

- [Original Adobe blog on usage data in Adobe Analytics](https://express.adobe.com/page/hnYfQPThMu2dr/)
- [Usage and Admin Logs API](https://developer.adobe.com/analytics-apis/docs/2.0/guides/endpoints/usage/)
- [Bulk Data Insertion API](https://developer.adobe.com/analytics-apis/docs/2.0/guides/endpoints/bulk-data-insertion/)

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
