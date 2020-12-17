# pylint: disable=line-too-long, no-member, chained-comparison
# -*- coding: utf-8 -*-

from __future__ import print_function

from builtins import str, object # pylint: disable=redefined-builtin

import datetime
import json
import logging
import time

import arrow
import requests

from past.utils import old_div

PDK_API_DEFAULT_PAGE_SIZE = 100

def post_request_with_retries(url, payload, max_retry_duration=120, initial_retry_duration=3.75, server_timeout=60):
    query = None
    last_error = None

    while initial_retry_duration <= max_retry_duration:
        try:
            query = None

            if server_timeout is not None:
                query = requests.post(url, data=payload, timeout=server_timeout)
            else:
                query = requests.post(url, data=payload)

            if query.status_code != 200:
                print('CODE: ' + str(query.status_code))

            if query.status_code == requests.codes.ok:
                return query
        except requests.exceptions.HTTPError as error:
            logging.warning(str(error))
            logging.warning('Retrying in %.2f seconds...', initial_retry_duration)

            last_error = error
        except requests.exceptions.Timeout as error:
            logging.warning(str(error))
            logging.warning('Retrying in %.2f seconds...', initial_retry_duration)

            last_error = error
        except requests.exceptions.ConnectionError as error:
            logging.warning(str(error))
            logging.warning('Retrying in %.2f seconds...', initial_retry_duration)

            last_error = error

        time.sleep(initial_retry_duration)

        initial_retry_duration *= 2

    if last_error is not None:
        raise last_error # pylint: disable=raising-bad-type

    raise Exception('Unknown error occurred.')

class PDKClient(object): # pylint: disable=useless-object-inheritance
    def __init__(self, **kwargs):
        self.site_url = kwargs['site_url']
        self.expires = None
        self.token = None
        self.timeout = None

        if 'token' in kwargs:
            self.token = kwargs['token']
        elif ('username' in kwargs) and ('password' in kwargs):
            self.generate_new_token(kwargs['username'], kwargs['password'])

        if 'timeout' in kwargs:
            self.timeout = kwargs['timeout']


    def generate_new_token(self, username, password):
        payload = {
            'username': username,
            'password': password,
        }

        fetch_token = post_request_with_retries(self.site_url + '/api/request-token.json', payload, server_timeout=self.timeout)

        if fetch_token.status_code == requests.codes.ok:
            response_payload = fetch_token.json()

            self.token = response_payload['token']
            self.expires = arrow.get(response_payload['expires']).datetime
        else:
            fetch_token.raise_for_status()


    def expired(self):
        if self.expires is None:
            return True

        now = arrow.utcnow().datetime

        return now > self.expires


    def connected(self):
        if self.expired():
            return False

        if self.token is None:
            return False

        return True

    def query_data_points(self, *args, **kwargs): # pylint: disable=unused-argument
        # Add filter to recorded field so data set does not grow as data is added while querying...

        now = arrow.utcnow().datetime

        return PDKDataPointQuery(self.token, self.site_url, self.timeout, **kwargs).filter(recorded__lte=now)

    def query_data_sources(self, *args, **kwargs): # pylint: disable=unused-argument
        return PDKDataSourceQuery(self.token, self.site_url, self.timeout, **kwargs).exclude(pk=None)


class PDKDataPointQuery(object): # pylint: disable=too-many-instance-attributes, useless-object-inheritance
    def __init__(self, token, site_url, timeout, *args, **kwargs): # pylint: disable=unused-argument
        self.token = token
        self.site_url = site_url
        self.timeout = timeout

        page_size = PDK_API_DEFAULT_PAGE_SIZE

        if 'page_size' in kwargs:
            page_size = kwargs['page_size']
            del kwargs['page_size']

        self.page_size = page_size

        self.filters = []
        self.excludes = []
        self.order_bys = []

        if kwargs:
            self.filters.append(kwargs)

        self.total_count = None
        self.page_index = 0
        self.current_index = 0

        self.current_page = None

    def filter(self, **kwargs):
        query = PDKDataPointQuery(self.token, self.site_url, self.page_size)

        query.filters = list(self.filters)
        query.excludes = list(self.excludes)
        query.order_bys = list(self.order_bys)

        query.filters.append(kwargs)

        return query

    def exclude(self, **kwargs):
        query = PDKDataPointQuery(self.token, self.site_url, self.page_size)

        query.filters = list(self.filters)
        query.excludes = list(self.excludes)
        query.order_bys = list(self.order_bys)

        query.excludes.append(kwargs)

        return query

    def order_by(self, *args):
        query = PDKDataPointQuery(self.token, self.site_url, self.page_size)

        query.filters = list(self.filters)
        query.excludes = list(self.excludes)
        query.order_bys = list(self.order_bys)

        query.order_bys.append(args)

        return query

    def count(self):
        if self.total_count is not None:
            return self.total_count

        self.load_page(0)

        return self.total_count

    def __iter__(self):
        self.load_page(0)

        return self

    def __next__(self):
        if self.current_index >= self.total_count:
            raise StopIteration

        if self.current_index >= (self.page_index + 1) * self.page_size:
            self.load_page(self.page_index + 1)

        value = self.current_page[self.current_index % self.page_size]

        self.current_index += 1

        return value

    def next(self):
        return self.__next__()

    def __getitem__(self, slice_item):
        if isinstance(slice_item, int): # pylint: disable=no-else-return
            index = slice_item

            if self.current_page is None:
                self.load_page(0)

            if index < 0:
                index = self.total_count + index

            if (index >= (self.page_index * self.page_size)) and (index < ((self.page_index + 1) * self.page_size)):
                return self.current_page[index % self.page_size]

            self.load_page(int(old_div(index, self.page_size)))

            return self.current_page[index % self.page_size]
        elif isinstance(slice_item, slice):
            logging.error('SLICE NOT YET SUPPORTED: %s', str(slice_item))

        return []

    def first(self):
        return self[0]

    def last(self):
        return self[-1]

    def load_page(self, page_number):
        self.page_index = page_number

        payload = {
            'token': self.token,
            'page_size': self.page_size,
            'page_index': self.page_index,
            'filters': json.dumps(self.filters, cls=DatetimeEncoder),
            'excludes': json.dumps(self.excludes, cls=DatetimeEncoder),
            'order_by': json.dumps(self.order_bys, cls=DatetimeEncoder),
        }

        fetch_page = post_request_with_retries(self.site_url + '/api/data-points.json', payload, server_timeout=self.timeout)

        if fetch_page.status_code == requests.codes.ok:
            response_payload = fetch_page.json()

            self.total_count = response_payload['count']
            self.page_index = response_payload['page_index']
            self.page_size = response_payload['page_size']

            self.current_page = response_payload['matches']
        else:
            fetch_page.raise_for_status()

class DatetimeEncoder(json.JSONEncoder):
    def default(self, obj): # pylint: disable=arguments-differ, method-hidden
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()

        try:
            return super(DatetimeEncoder, obj).default(obj)
        except TypeError:
            return str(obj)


class PDKDataSourceQuery(object): # pylint: disable=too-many-instance-attributes, useless-object-inheritance
    def __init__(self, token, site_url, timeout, *args, **kwargs): # pylint: disable=unused-argument
        self.token = token
        self.site_url = site_url
        self.timeout = timeout

        page_size = PDK_API_DEFAULT_PAGE_SIZE

        if 'page_size' in kwargs:
            page_size = kwargs['page_size']
            del kwargs['page_size']

        self.page_size = page_size

        self.filters = []
        self.excludes = []
        self.order_bys = []

        if kwargs:
            self.filters.append(kwargs)

        self.total_count = None
        self.page_index = 0
        self.current_index = 0

        self.current_page = None

    def filter(self, **kwargs):
        query = PDKDataSourceQuery(self.token, self.site_url, self.page_size)

        query.filters = list(self.filters)
        query.excludes = list(self.excludes)
        query.order_bys = list(self.order_bys)

        query.filters.append(kwargs)

        return query

    def exclude(self, **kwargs):
        query = PDKDataSourceQuery(self.token, self.site_url, self.page_size)

        query.filters = list(self.filters)
        query.excludes = list(self.excludes)
        query.order_bys = list(self.order_bys)

        query.excludes.append(kwargs)

        return query

    def order_by(self, *args):
        query = PDKDataSourceQuery(self.token, self.site_url, self.page_size)

        query.filters = list(self.filters)
        query.excludes = list(self.excludes)
        query.order_bys = list(self.order_bys)

        query.order_bys.append(args)

        return query

    def count(self):
        if self.total_count is not None:
            return self.total_count

        self.load_page(0)

        return self.total_count

    def __iter__(self):
        self.load_page(0)

        return self

    def __next__(self):
        if self.current_index >= self.total_count:
            raise StopIteration

        if self.current_index >= (self.page_index + 1) * self.page_size:
            self.load_page(self.page_index + 1)

        value = self.current_page[self.current_index % self.page_size]

        self.current_index += 1

        return value

    def next(self):
        return self.__next__()

    def __getitem__(self, slice_item):
        if isinstance(slice_item, int): # pylint: disable=no-else-return
            index = slice_item

            if self.current_page is None:
                self.load_page(0)

            if index < 0:
                index = self.total_count + index

            if (index >= (self.page_index * self.page_size)) and (index < ((self.page_index + 1) * self.page_size)):
                return self.current_page[index % self.page_size]

            self.load_page(int(old_div(index, self.page_size)))

            return self.current_page[index % self.page_size]
        elif isinstance(slice_item, slice):
            logging.error('SLICE NOT YET SUPPORTED: %s', str(slice_item))

        return []

    def first(self):
        return self[0]

    def last(self):
        return self[-1]

    def load_page(self, page_number):
        self.page_index = page_number

        payload = {
            'token': self.token,
            'page_size': self.page_size,
            'page_index': self.page_index,
            'filters': json.dumps(self.filters, cls=DatetimeEncoder),
            'excludes': json.dumps(self.excludes, cls=DatetimeEncoder),
            'order_by': json.dumps(self.order_bys, cls=DatetimeEncoder),
        }

        fetch_page = post_request_with_retries(self.site_url + '/api/data-sources.json', payload, server_timeout=self.timeout)

        if fetch_page.status_code == requests.codes.ok:
            response_payload = fetch_page.json()

            self.total_count = response_payload['count']
            self.page_index = response_payload['page_index']
            self.page_size = response_payload['page_size']

            self.current_page = response_payload['matches']
        else:
            fetch_page.raise_for_status()
