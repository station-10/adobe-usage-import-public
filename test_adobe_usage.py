"""
Test module for adobe_usage.py

To run tests:
    pytest -v test_adobe_usage.py
    pytest -v test_adobe_usage.py::TestInclusiveDateRange
    pytest -v test_adobe_usage.py::TestInclusiveDateRange::test_inclusive_date_range_same_date
    etc
"""

from datetime import datetime, timedelta
import json
import os
import tempfile
import pytest
from adobe_usage import AdobeAPI


class TestInclusiveDateRange:
    """Test class for inclusive_date_range()"""

    @pytest.fixture
    def your_class_instance(self):
        """Fixture to instantiate your class"""
        return AdobeAPI()

    def test_inclusive_date_range_same_date(self, your_class_instance):
        """Test inclusive_date_range() with same start and end date"""
        start_date = "2021-09-01"
        end_date = "2021-09-01"
        expected_start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        expected_end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(
            days=1, seconds=-1
        )
        result = your_class_instance.inclusive_date_range(start_date, end_date)
        assert result == (expected_start_dt, expected_end_dt)

    def test_inclusive_date_range_different_dates(self, your_class_instance):
        """Test inclusive_date_range() with different start and end date"""
        start_date = "2021-09-01"
        end_date = "2021-09-03"
        expected_start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        expected_end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(
            days=1, seconds=-1
        )
        result = your_class_instance.inclusive_date_range(start_date, end_date)
        assert result == (expected_start_dt, expected_end_dt)

    def test_inclusive_date_range_invalid_date_format(self, your_class_instance):
        """Test inclusive_date_range() with invalid date format"""
        start_date = "2021/09/01"
        end_date = "2021/09/03"
        with pytest.raises(ValueError):
            your_class_instance.inclusive_date_range(start_date, end_date)

    def test_inclusive_date_range_invalid_dates(self, your_class_instance):
        """Test inclusive_date_range() with start date after end date"""
        start_date = "2021-09-03"
        end_date = "2021-09-01"
        with pytest.raises(ValueError):
            your_class_instance.inclusive_date_range(start_date, end_date)

    def test_inclusive_date_range_leap_year(self, your_class_instance):
        """Test inclusive_date_range() with leap year"""
        start_date = "2020-02-28"
        end_date = "2020-03-01"
        expected_start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        expected_end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(
            days=1, seconds=-1
        )
        result = your_class_instance.inclusive_date_range(start_date, end_date)
        assert result == (expected_start_dt, expected_end_dt)


class TestUpdateEventTypes:
    """Test class for update_event_types()"""

    @pytest.fixture
    def your_class_instance_instance(self):
        """Fixture to instantiate your class"""
        return AdobeAPI()

    @pytest.fixture
    def json_data(self):
        """Fixture to provide sample JSON data"""
        return [
            {"eventType": "0"},  # No Category
            {"eventType": "1"},  # Login failed
            {"eventType": "61"},  # Api Method
            {"eventType": "9999"},  # Unknown Event Type: 9999
            {"eventType": 2},  # Number, should still return "Login successful"
        ]

    @pytest.fixture
    def json_file(self, json_data):
        """Fixture to create a temporary JSON file"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
            json.dump(json_data, temp_file)
            temp_file.flush()
        yield temp_file.name
        os.remove(temp_file.name)

    def test_update_event_types(self, your_class_instance_instance, json_file):
        """Test update_event_types() with a sample JSON file"""
        your_class_instance_instance.update_event_types(json_file)

        with open(json_file, "r", encoding="utf-8") as updated_file:
            updated_data = json.load(updated_file)

        assert updated_data[0]["eventType"] == "No Category"
        assert updated_data[1]["eventType"] == "Login failed"
        assert updated_data[2]["eventType"] == "Api Method"
        assert updated_data[3]["eventType"] == "Unknown Event Type: 9999"
        assert updated_data[4]["eventType"] == "Login successful"

    def test_update_event_types_empty_json_file(self, your_class_instance_instance):
        """Test update_event_types() with an empty JSON file"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
            json.dump([], temp_file)
            temp_file.flush()
            empty_json_file = temp_file.name

        your_class_instance_instance.update_event_types(empty_json_file)

        with open(empty_json_file, "r", encoding="utf-8") as updated_file:
            updated_data = json.load(updated_file)

        assert updated_data == []

        os.remove(empty_json_file)


class TestAddComponentInfo:
    """Test class for add_component_info()"""

    @pytest.fixture
    def your_class_instance(self):
        """Fixture to instantiate your class"""
        return AdobeAPI()

    @pytest.fixture
    def sample_event_descriptions(self):
        """Fixture to provide sample JSON data"""
        return [
            {
                "eventDescription": "Segment Created: Name=Target Activities = Test 26 - Popular Categories Design V2 - Live Id=s3954_621cd43a89b6ad49703259b5 Owner=Jane Smith"
            },
            {
                "eventDescription": "Calculated Metric Created: Name=Cash Application Success (e1) Calculated Metric Id=cm3954_621cc07532a5796d562f2909 Owner=John Smith"
            },
            {
                "eventDescription": "Segment Updated: Name=Product Brand = Celotex OR ISOVER Segment Id=s3954_611b8639bd1b3b1ffc3fdffc"
            },
            {
                "eventDescription": "Project Viewed: Name=Accutics QA - Campaign Builder & Cost Importer Project Id=61c0b641e4a6c16bf1763cfe Owner=Steve Webb"
            },
            {
                "eventDescription": "Segment Updated: Name=Hit - Exclude LSFGGSL6 Segment Id=s3954_621c91e0fa093118dc8a2146 Owner=David Smith"
            },
            {
                "eventDescription": "Segment Created: Name=UTM Medium (v62) equals any of cpc Segment Id=s3954_6219d0b95315df22f82c3471 Owner=Dave Smith"
            },
        ]

    @pytest.fixture
    def temp_json_file(self, sample_event_descriptions):
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as temp_file:
            json.dump(sample_event_descriptions, temp_file)
            temp_file.flush()

        yield temp_file.name

        os.remove(temp_file.name)

    def test_add_component_info(self, your_class_instance, temp_json_file):
        your_class_instance.add_component_info(temp_json_file)

        with open(temp_json_file, "r", encoding="utf-8") as json_file:
            updated_data = json.load(json_file)

        assert len(updated_data) == 6

        assert (
            updated_data[0]["componentName"]
            == "Target Activities = Test 26 - Popular Categories Design V2 - Live"
        )
        assert updated_data[0]["componentId"] == "s3954_621cd43a89b6ad49703259b5"
        assert updated_data[0]["componentOwner"] == "Jane Smith"

        assert (
            updated_data[1]["componentName"]
            == "Cash Application Success (e1) Calculated Metric"
        )
        assert updated_data[1]["componentId"] == "cm3954_621cc07532a5796d562f2909"
        assert updated_data[1]["componentOwner"] == "John Smith"

        assert (
            updated_data[2]["componentName"]
            == "Product Brand = Celotex OR ISOVER Segment"
        )
        assert updated_data[2]["componentId"] == "s3954_611b8639bd1b3b1ffc3fdffc"
        assert updated_data[2]["componentOwner"] == "N/A"

        assert (
            updated_data[3]["componentName"]
            == "Accutics QA - Campaign Builder & Cost Importer Project"
        )
        assert updated_data[3]["componentId"] == "61c0b641e4a6c16bf1763cfe"
        assert updated_data[3]["componentOwner"] == "Steve Webb"

        assert updated_data[4]["componentName"] == "Hit - Exclude LSFGGSL6 Segment"
        assert updated_data[4]["componentId"] == "s3954_621c91e0fa093118dc8a2146"
        assert updated_data[4]["componentOwner"] == "David Smith"

        assert (
            updated_data[5]["componentName"]
            == "UTM Medium (v62) equals any of cpc Segment"
        )
        assert updated_data[5]["componentId"] == "s3954_6219d0b95315df22f82c3471"
        assert updated_data[5]["componentOwner"] == "Dave Smith"
