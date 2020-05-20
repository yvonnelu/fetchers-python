import logging
import pandas as pd
from utils.fetcher_abstract import AbstractFetcher
from datetime import datetime
import os
import sys

__all__ = ('EU_ZH_Fetcher',)

logger = logging.getLogger(__name__)

"""
    site-location: https://github.com/covid19-eu-zh/covid19-eu-data

    COVID19 data for European countries created and maintained by covid19-eu-zh

    Data originally from

    Austria's Sozial Ministerium https://www.sozialministerium.at/Informationen-zum-Coronavirus/Neuartiges-Coronavirus-(2019-nCov).html
    Czech Ministry of Health https://onemocneni-aktualne.mzcr.cz/covid-19
    Germany's Robert Koch Institute https://www.rki.de/DE/Content/InfAZ/N/Neuartiges_Coronavirus/Fallzahlen.html
    Hungary's Office of the Prime Minister https://koronavirus.gov.hu/
    Ireland's Health Protection Surveillance Centre https://www.hpsc.ie/a-z/respiratory/coronavirus/novelcoronavirus/casesinireland/
    Poland - Government https://www.gov.pl/web/koronawirus/wykaz-zarazen-koronawirusem-sars-cov-2
    Sweden's Public Health Authority https://www.folkhalsomyndigheten.se/smittskydd-beredskap/utbrott/aktuella-utbrott/covid-19/aktuellt-epidemiologiskt-lage/
    Slovenia's Government Communications Office https://www.gov.si/en/topics/coronavirus-disease-covid-19/
"""


class EU_ZH_Fetcher(AbstractFetcher):
    LOAD_PLUGIN = True

    def fetch(self, url):
        return pd.read_csv(url)

    # Certain regions have excess characters in some source files
    def clean_string(self, input):
        if isinstance(input, str):
            return input.replace('­', '')
        else:
            return input

    def country_fetcher(self, region, country, code_3, code_2):

        logger.info("Processing number of cases in " + country)

        if code_3 == 'NOR':
            logger.warning("These GIDs not entirely accurate due to change in Norway's county boundaries, 2020.")

        url = 'https://github.com/covid19-eu-zh/covid19-eu-data/raw/master/dataset/covid-19-' + code_2 + '.csv'
        df = self.fetch(url)

        for index, record in df.iterrows():

            # date must be reformatted
            d = record['datetime']
            date = datetime.strptime(d, '%Y-%m-%dT%H:%M:%S').strftime('%Y-%m-%d')

            # If no region is reported then all data is national
            if not hasattr(record, region):
                adm_area_1 = None
                gid = [code_3]
            # Ignore two known corrupted lines in the Polish data
            elif str(record[region])[:4] == 'http':
                continue
            elif pd.isna(record[region]) and code_3 == 'POL':
                continue
            # Austria's national data is reported with a blank region
            elif pd.isna(record[region]) and code_3 == 'AUT':
                adm_area_1 = None
                gid = [code_3]
            # If the region appears cleanly, then we can translate to obtain GID
            else:
                success, adm_area_1, adm_area_2, adm_area_3, gid = self.adm_translator.tr(
                    input_adm_area_1=self.clean_string(record[region]),
                    input_adm_area_2=None,
                    input_adm_area_3=None,
                    return_original_if_failure=True,
                    suppress_exception=True
                )

            # we need to build an object containing the data we want to add or update
            upsert_obj = {
                'source': 'COVID19-EU-ZH',
                'date': date,
                'country': country,
                'countrycode': code_3,
                'adm_area_1': adm_area_1,
                'adm_area_2': None,
                'adm_area_3': None,
                'gid': gid
            }

            # add the epidemiological properties to the object if they exist
            if hasattr(record, 'tests'):
                tested = int(record['tests']) if pd.notna(record['tests']) else None
                upsert_obj['tested'] = tested
            if hasattr(record, 'cases'):
                confirmed = int(record['cases']) if pd.notna(record['cases']) else None
                upsert_obj['confirmed'] = confirmed
            if hasattr(record, 'tests_positive'):
                confirmed = int(record['tests_positive']) if pd.notna(record['tests_positive']) else None
                upsert_obj['confirmed'] = confirmed
            if hasattr(record, 'recovered'):
                recovered = int(record['recovered']) if pd.notna(record['recovered']) else None
                upsert_obj['recovered'] = recovered
            if hasattr(record, 'deaths'):
                dead = int(record['deaths']) if pd.notna(record['deaths']) else None
                upsert_obj['dead'] = dead
            if hasattr(record, 'hospitalized'):
                hospitalised = int(record['hospitalized']) if pd.notna(record['hospitalized']) else None
                upsert_obj['hospitalised'] = hospitalised
            if hasattr(record, 'intensive_care'):
                hospitalised_icu = int(record['intensive_care']) if pd.notna(record['intensive_care']) else None
                upsert_obj['hospitalised_icu'] = hospitalised_icu
            if hasattr(record, 'quarantine'):
                quarantine = int(record['quarantine']) if pd.notna(record['quarantine']) else None
                upsert_obj['quarantined'] = quarantine

            self.db.upsert_epidemiology_data(**upsert_obj)

    # read the list of countries from a csv file in order to fetch each one
    def load_countries_to_fetch(self):
        input_csv_fname = getattr(self.__class__, 'INPUT_CSV', "input.csv")
        path = os.path.dirname(sys.modules[self.__class__.__module__].__file__)
        csv_fname = os.path.join(path, input_csv_fname)
        if not os.path.exists(csv_fname):
            return None
        colnames = ['country', 'code_3', 'code_2', 'region']
        input_pd = pd.read_csv(csv_fname)
        input_pd.columns = colnames
        input_pd = input_pd.where((pd.notnull(input_pd)), None)
        return input_pd

    def run(self):
        countries = self.load_countries_to_fetch()
        for index, record in countries.iterrows():
            self.country_fetcher(record['region'], record['country'], record['code_3'], record['code_2'])