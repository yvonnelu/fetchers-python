import logging
import requests
from .utils import parser

from utils.fetcher_abstract import AbstractFetcher

__all__ = ('StringencyFetcher',)

logger = logging.getLogger(__name__)


class StringencyFetcher(AbstractFetcher):
    LOAD_PLUGIN = True

    def fetch(self):
        date_from = '2020-01-01'
        date_to = '2021-01-01'
        api_data = requests.get(
            f'https://covidtrackerapi.bsg.ox.ac.uk/api/stringency/date-range/{date_from}/{date_to}').json()
        return parser(api_data)

    def run(self):
        govtrack_data = self.fetch()
        for index, record in govtrack_data.iterrows():
            upsert_obj = {
                'source': 'GOVTRACK',
                'date': record['date_value'],
                'country': record['English short name lower case'],
                'countrycode': record['country_code'],
                'confirmed': int(record['confirmed']),
                'dead': int(record['deaths']),
                'stringency': int(record['stringency']),
                'stringency_actual': int(record['stringency_actual'])
            }
            self.db.upsert_govtrack_data(**upsert_obj)