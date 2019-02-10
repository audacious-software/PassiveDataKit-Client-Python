# -*- coding: utf-8 -*-

from __future__ import print_function

import datetime
import json
import sys

import arrow
import requests 

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

class PDKClient:
    def __init__(self, *args, **kwargs):
        self.site_url = kwargs['site_url']
        self.expires = None
        self.token = None
        
        if ('username' in kwargs) and ('password' in kwargs):
            self.generate_new_token(kwargs['username'], kwargs['password'])


    def generate_new_token(self, username, password):
        payload = {
            'username': username,
            'password': password,
        }
        
        r = requests.post(self.site_url + '/api/request-token.json', data=payload)
        
        if r.status_code == requests.codes.ok:
            response_payload = r.json()
            
            self.token = response_payload['token']
            self.expires = arrow.get(response_payload['expires']).datetime
        else:
            r.raise_for_status()


    def expired(self):
        if self.expires is None:
            return True

        now = arrow.utcnow().datetime
        
        return (now > self.expires)


    def connected(self):
        if self.expired():
            return False
        
        if self.token is None:
            return False
            
        return True

    
    def query_data_points(self, page_size=500, *args, **kwargs):
    	# Add filter to recorded field so data set does not grow as data is added while querying...
    	
    	now = arrow.utcnow().datetime
    	
        return PDKDataPointQuery(self.token, self.site_url, page_size=page_size, **kwargs).filter(recorded__lte=now)
    
    
class PDKDataPointQuery:
    def __init__(self, token, site_url, page_size=500, *args, **kwargs):
        self.token = token
        self.site_url = site_url
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
        
    def filter(self, *args, **kwargs):
        query = PDKDataPointQuery(self.token, self.site_url, self.page_size)
        
        query.filters = list(self.filters)
        query.excludes = list(self.excludes)
        query.order_bys = list(self.order_bys)
        
        query.filters.append(kwargs)
        
        return query

    def exclude(self, *args, **kwargs):
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

    def next(self):
        if self.current_index >= self.count:
            raise StopIteration

        if self.current_index >= self.page_index * self.page_size:
            self.load_page(self.page_index + 1)
            
        value = self.current_page[self.current_index % self.page_size]
        
        self.current_index += 1

        return value

    def __getitem__(self, slice_item):
        if isinstance(slice_item, (int, long)):
            index = slice_item

            if self.current_page is None:
                self.load_page(0)

            if index < 0:
                index = self.total_count + index
            
            if (index >= (self.page_index * self.page_size)) and (index < ((self.page_index + 1) * self.page_size)):
                return self.current_page[index % self.page_size]
            else:
                self.load_page(int(index / self.page_size))

                return self.current_page[index % self.page_size]
        elif isinstance(slice_item, slice):
            eprint('SLICE NOT YET SUPPORTED: ' + str(slice_item))
            return []


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
        
        r = requests.post(self.site_url + '/api/data-points.json', data=payload)
        
        if r.status_code == requests.codes.ok:
            response_payload = r.json()
            
            self.total_count = response_payload['count']
            self.page_index = response_payload['page_index']
            self.page_size = response_payload['page_size']
            
            self.current_page = response_payload['matches']
        else:
            r.raise_for_status()

class DatetimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
            
        try:
            return super(DatetimeEncoder, obj).default(obj)
        except TypeError:
            return str(obj)
