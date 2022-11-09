# racktables2netbox
A [RackTables](https://github.com/racktables/racktables) to [NetBox](https://github.com/digitalocean/netbox) migration utility. This tiny tool should be used to migrate your existing RackTables installations towards NetBox.

Reccomended racktables source version 0.21.X

## Known Issues
1. Racktables allows an object to be "split" across U's, netbox does not. split these up in racktables pre-migration. (eg, a device in U1 and U3, but not in U2)
2. Netbox needs device templates, you will need to populate hardware_map.yaml with mappings between racktables device types to nb device types

## Installation
```curl --output racktables2netbox.zip https://github.com/ITJamie/racktables2netbox/archive/master.zip
unzip racktables2netbox.zip
cd racktables2netbox
cp conf.sample.yaml conf.yaml
cp hardware_map.yaml.sample hardware_map.yaml
```

## Usage
1. Create a NetBox API Token
2. Create a RackTables read-only database user
3. edit ``conf.yaml`` regarding your needs (URLs, credentials, ...)
4. run `python3 racktables2netbox.py`
5. optional: to get back to a clean NetBox installation run `python3 clean_netbox.py`

## Contributing
1. Fork it (<https://github.com/yourname/yourproject/fork>)
2. Create your feature branch (`git checkout -b feature/fooBar`)
3. Commit your changes (`git commit -am 'Add some fooBar'`)
4. Push to the branch (`git push origin feature/fooBar`)
5. Create a new Pull Request

## Credits
Thanks to [Device42](https://www.device42.com/) who have already written a [RackTables to Device42 migration utility](https://github.com/device42/Racktables-to-Device42-Migration). @goebelmeier was able to use it as a starting point to make this migration script.
ITJamie forked it and added more data migrations. I am trying to get it to work for our operations.

## License
racktables2netbox is licensed under MIT license. See [LICENSE.md](LICENSE.md) for more information.
