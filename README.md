# passive-data-kit-client

*This library is **still under construction**. Do not use in stable contexts as
the implementation is likely to change.*

This library implements a Python client library for accessing a Passive Data 
Kit (PDK) server and querying data into a local context with all of the relevant 
logging and auditing in place server-side. It uses Django queries as an 
inspiration and functions very similarly.

## Usage

    from pdk_client import PDKClient
    
    # Create a client object.
    client = PDKClient(site_url=SITE_URL, username=USERNAME, password=PASSWORD)
    
    # Create a data point query object
    query = client.query_data_points(page_size=PAGE_SIZE)
    
    # Return the total number of data points on the server.
    query.count()
    
    # Create a new query object that constrains it to a specific data source.
    new_query = query.filter(source='source-id')
    new_query.count()
    
    # Get the first observed data point for a specific generator.
    new_query = query.filter(source='source-id', generator_identifier='pdk-device-battery').order_by('created')
    first_battery_point = new_query[0]
    
    # Get the most recently observed point, instead.
    last_battery_point = new_query[-1]
    
    # Iterate over all matching items in query.
    for point in new_query:
        print(json.dumps(point, indent=2))

    # Get the data points for a specific generator, excluding specific source.
    exclude_query = query.filter(generator_identifier='pdk-device-battery').exclude(source='source-id').order_by('created')
    
## Notes

Behind the scenes, this library obtains a time-limited token for querying the 
PDK server on client creation. Parameters:

* `site_url`: URL prefix of the PDK installation. (Example: `https://mysite/data/`)
* `username`: Username of authorized PDK user.
* `password`: Password of authorized PDK user.

Upon fetching the authentication token, the library discards the password for 
the remainder of operations, using the token instead. The state of the token 
may be checked while in use:
    
    from pdk_client import PDKClient
    
    # Create a client object.
    client = PDKClient(site_url=SITE_URL, username=USERNAME, password=PASSWORD)
    
    # Returns True if the token has expired and a new client should be created, False otherwise.
    is_expired = client.expired()
    
    # Returns datetime.datetime object encoding the expiration date.
    when_expires = client.expires()

    # Returns True if the client is authorized to communicate with the server, False otherwise.
    # May change when the token expires.
    is_connected = client.connected()
    
When a query object is obtained, the `page_size` parameter may be passed to 
control the number and size of queries:

    query = client.query_data_points(page_size=PAGE_SIZE)

The library uses paging internally to provide a Python list-like interface for 
accessing the data from the server. Since the size of the available data may 
exceed memory and bandwidth resources, this allows the necessary work to be 
decomposed into workable chunks. Internally, the library also adds an 
additional constraint where the data returned will be the data present on the
server at the time of the `PDKClient.query_data_points` call, eliminating 
any unexpected behavior where data may be added to the server while the query
is in use.
    
When constraining the query using `filter` or `excludes` functions, these 
functions are mapped onto their Django equivalents on the PDK server. Arguments
on corresponding server `Data Point` objects are supported, as well as any 
special arguments supported by the remote server, such as [JSONField queries](https://docs.djangoproject.com/en/1.11/ref/contrib/postgres/fields/#querying-jsonfield)
on modern Postgres servers:

    query.filter(properties__application__icontains='youtube').count()

## Installation

The package is intended to be installed with `pip`:

    pip install git+https://github.com/audaciouscode/PassiveDataKit-Client-Python.git

When the library reaches maturity, it will be made available on PyPi as 
`passive-data-kit-client`.

## Major Outstanding Items

The following items are on the roadmap for support:

* Support for querying other Passive Data Kit types: data sources, alerts, exports.
* Support for [Q-object](https://docs.djangoproject.com/en/1.11/topics/db/queries/#complex-lookups-with-q-objects) equivalents, supporting more flexible Boolean parameters.
* Support for renewing tokens.
* Full support for [slices](https://www.w3schools.com/python/ref_func_slice.asp) in querys. 
  Currently items may be accessed by index, but not range.

If you encounter any bugs or other issues, please [add an issue](https://github.com/audaciouscode/PassiveDataKit-Client-Python/issues).
