import json
from cStringIO import StringIO
from healthtools.scrapers.base_scraper import Scraper
from healthtools.config import AWS
import requests
import boto3


health_facilities_template = """
    {
     "type": "add",
     "id":   "%s",
     "fields": {
              "name": "%s",
              "facility_type_name": "%s",
              "approved": "%s",
              "sub_county_name": "%s",
              "service_names": "%s",
              "county_name": "%s",
              "open_public_holidays": "%s",
              "keph_level_name": "%s",
              "open_whole_day": "%s",
              "owner_name": "%s",
              "constituency_name": "%s",
              "regulatory_body_name": "%s",
              "operation_status_name": "%s",
              "open_late_night": "%s",
              "open_weekends": "%s",
              "ward_name": "%s"
            }
    }"""
delete_template = """
    {
    "type": "delete",
    "id" : "%s"
    }"""
TOKEN_URL = 'http://api.kmhfl.health.go.ke/o/token/'
SEARCH_URL = 'http://api.kmhfl.health.go.ke/api/facilities/material/?page_size=100000&' \
             'fields=id,regulatory_status_name,facility_type_name,facility_type_parent,owner_name,owner_type_name,' \
             'owner_type,operation_status_name,county,constituency,constituency_name,ward_name,average_rating,' \
             'facility_services,is_approved,has_edits,latest_update,regulatory_body_name,owner,date_requested,' \
             'date_approved,latest_approval_or_rejection,sub_county_name,sub_county_id,county_name,constituency_id,' \
             'county_id,keph_level_name,facility_contacts,coordinates,lat_long,latest_approval,county_code,constituency_code' \
             ',ward_code,service_catalogue_active,facility_units,officer_in_charge,created,updated,deleted,active,search,' \
             'name,official_name,code,registration_number,abbreviation,description,number_of_beds,number_of_cots,' \
             'open_whole_day,open_public_holidays,open_normal_day,open_weekends,open_late_night,is_classified,' \
             'is_published,regulated,approved,rejected,bank_name,branch_name,bank_account,facility_catchment_population,' \
             'town_name,nearest_landmark,plot_number,location_desc,closed,closed_date,closing_reason,date_established,' \
             'license_number,created_by,updated_by,facility_type,operation_status,ward,parent,regulatory_body,' \
             'keph_level,sub_county,town,regulation_status,contacts&format=json'


class HealthFacilitiesScraper(Scraper):
    def __init__(self):
        super(HealthFacilitiesScraper, self).__init__()
        self.access_token = None
        self.s3_key = "data/health_facilities.json"
        self.s3_historical_record_key = "data/archive/health_facilities-{}.json"
        self.delete_file = "data/delete_health_facilities.json"
        self.cloudsearch = boto3.client(
            "cloudsearchdomain", **{
                "aws_access_key_id": AWS["aws_access_key_id"],
                "aws_secret_access_key": AWS["aws_secret_access_key"],
                "region_name": AWS["region_name"],
                "endpoint_url": AWS["cloudsearch_health_faciities_endpoint"]
            })

    def get_token(self):
        print "Running HealthFacilitiesScraper"
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        data = {
            'username': 'public@mfltest.slade360.co.ke',
            'password': 'public',
            'grant_type': 'password',
            'client_id': 'xMddOofHI0jOKboVxdoKAXWKpkEQAP0TuloGpfj5',
            'client_secret': 'PHrUzCRFm9558DGa6Fh1hEvSCh3C9Lijfq8sbCMZhZqmANYV5ZP04mUXGJdsrZLXuZG4VCmvjShdKHwU6IRmPQld5LDzvJoguEP8AAXGJhrqfLnmtFXU3x2FO1nWLxUx'
        }
        r = requests.post(TOKEN_URL, data=data, headers=headers)
        self.access_token = json.loads(r.text)['access_token']

    def get_data(self):
        try:
            headers = {'Authorization': 'Bearer ' + self.access_token}
            r = requests.get(SEARCH_URL, headers=headers)
            data = r.json()
            payload = ''
            delete_payload = ''
            for i, record in enumerate(data['results']):
                payload += self.index_for_cloudsearch(record) + ','
                delete_payload += self.delete_payload(record) + ','
            payload = '[%s]' % payload[:-1] #remove last comma
            delete_payload = '[%s]' % delete_payload[:-1] #remove last comma
            self.delete_cloudsearch_docs() #delete cloudsearch data
            self.upload_data(payload) #upload data to cloudsearch
            print "| HealthFacilitiesScraper completed. | {} entries retrieved.".format(len(data['results']))
            # Push the data to s3
            self.archive_data(payload)

            # Push the delete payload to s3
            delete_file = StringIO(delete_payload)
            self.s3.upload_fileobj(
                delete_file, "cfa-healthtools-ke",
                self.delete_file)

            print " "
        except Exception, err:
            print "ERROR IN - index_for_search() - %s" % (err)

    def index_for_cloudsearch(self, record):
        return health_facilities_template  % (
            record['code'],
            record['name'].replace("\"", "'"),
            record['facility_type_name'],
            record['approved'],
            record['sub_county_name'],
            record['service_names'],
            record['county_name'],
            record['open_public_holidays'],
            record['keph_level_name'],
            record['open_whole_day'],
            record['owner_name'],
            record['constituency_name'],
            record['regulatory_body_name'],
            record['operation_status_name'],
            record['open_late_night'],
            record['open_weekends'],
            record['ward_name'].decode("string_escape").replace('\\', ''),
            )

    def delete_payload(self, record):
        return delete_template %(record['code'])
