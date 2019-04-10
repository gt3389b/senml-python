"""@package senml.senml
SenML Python object representation

@todo Add CBOR support
"""

import attr
import time
#try:
#    import cbor
#except ImportError:
#    HAVE_CBOR = False
#else:
#    HAVE_CBOR = True

@attr.s
class SenMLMeasurement(object):
    """SenML data representation"""
    name = attr.ib(default=None)
    time = attr.ib(default=None)
    unit = attr.ib(default=None)
    value = attr.ib(default=None)
    sum = attr.ib(default=None)
    update_time = attr.ib(default=None)
    version = attr.ib(default=None)

    def to_absolute(self, base):
        """Convert values to include the base information

        Be aware that it is not possible to compute time average of the signal
        without the base object since the base time and base value are still
        needed for that use case."""
        attrs = {
            'name': (base.name or '') + (self.name or ''),
            'time': (base.time or 0) + (self.time or 0),
            'unit': self.unit or base.unit,
            'update_time': self.update_time,
        }
        if base.sum or self.sum:  # If none of them exists, the field should not exist.
            attrs['sum'] = (base.sum or 0) + (self.sum or 0)

        if isinstance(self.value, (bool, bytes, str)):
            attrs['value'] = self.value
        elif (self.value or base.value) is not None:
            attrs['value'] = (base.value or 0) + (self.value or 0)

        """Convert relative time to absolute time"""
        t = ((base.time or 0) + (self.time or 0))
        if t < 268435456:
            epoch_time_now = time.time()
            attrs['time'] = t + epoch_time_now
        else:
            attrs['time'] = t
        ret = self.__class__(**attrs)
        return ret

    @classmethod
    def base_from_json(cls, data, version_set):
        """Create a base instance from the given SenML data"""
        template = cls()
        attrs = {
            'name':    data.get('bn', template.name),
            'time':    data.get('bt', template.time),
            'unit':    data.get('bu', template.unit),
            'value':   data.get('bv', template.value),
            'sum':     data.get('bs', template.sum),
            'version': data.get('bver', template.version),
        }
        # Convert to numeric types
        cls.clean_attrs(attrs)
        base_version = attrs.get('version')
        if base_version and version_set is not None:
            version_set.add(base_version)

        return cls(**attrs)

    @classmethod
    def update_base(cls, base, record, version_set):
        new_base = cls.base_from_json(record, version_set)
        if base is None:
            return new_base

        if new_base.name is not None:
            base.name = new_base.name
        if new_base.time is not None:
            base.time = new_base.time
        if new_base.unit is not None:
            base.unit = new_base.unit
        if new_base.value is not None:
            base.value = new_base.value
        if new_base.sum is not None:
            base.sum = new_base.sum
        if new_base.version is not None:
            base.version = new_base.version
        return base

    @staticmethod
    def numeric(val):
        """Convert val to int if the value does not have any decimals, else convert to float"""
        if val is None or isinstance(val, (float, int)):
            return val
        if float(val) == int(float(val)):
            return int(val)
        return float(val)

    @classmethod
    def clean_attrs(cls, attrs):
        """Clean broken SenML+JSON with strings where there are supposed to be numbers"""
        # This fixes common typing errors such as:
        # [{"bn":"asdf","bt":"1491918634"}]
        # (where the value for bt: is supposed to be a numeric type, not a string)
        for key in ('time', 'sum', 'value', 'version'):
            val = attrs.get(key, None)
            attrs[key] = cls.numeric(val)

    @staticmethod
    def is_valid(measurement, data):
        """Check that name is not empty"""
        if measurement.get('name') == "":
            return False

        """Check that a value key exist"""
        if measurement.get("value") is None:
            keys = ["bn", "bt", "bu", "bv", "bs", "bver"]
            if any(key in data for key in keys):
                return False
            else:
                raise Exception('Invalid SenML message')
        return True

    @classmethod
    def from_json(cls, data):
        """Create an instance given JSON data as a dict"""
        template = cls()
        attrs = {
            'name':        data.get('n', template.name),
            'time':        data.get('t', template.time),
            'unit':        data.get('u', template.unit),
            'value':       data.get('v', template.value),
            'sum':         data.get('s', template.sum),
            'update_time': data.get('ut', template.update_time)
        }
        # Convert to numeric types
        cls.clean_attrs(attrs)

        if attrs['value'] is None:
            if 'vs' in data:
                attrs['value'] = str(data['vs'])
            elif 'vb' in data:
                if str(data['vb']).casefold() == 'false'.casefold() or \
                        str(data['vb']).casefold() == '0'.casefold():
                    attrs['value'] = False
                else:
                    attrs['value'] = True
            elif 'vd' in data:
                attrs['value'] = bytes(data['vd'])
        elif isinstance(attrs['value'], int):
            attrs['value'] = float(attrs['value'])  # Comply with rfc8428 that the v field is for floating point.

        if cls.is_valid(attrs, data):
            return cls(**attrs)
        return None

    def to_json(self):
        """Format the entry as a SenML+JSON object"""
        ret = {}
        if self.name is not None:
            ret['n'] = str(self.name)

        if self.time is not None:
            ret['t'] = self.numeric(self.time)

        if self.unit is not None:
            ret['u'] = str(self.unit)

        if self.sum is not None:
            ret['s'] = self.numeric(self.sum)

        if self.update_time is not None:
            ret['ut'] = self.numeric(self.update_time)

        if self.version is not None:
            ret['bver'] = self.version

        if isinstance(self.value, bool):
            ret['vb'] = self.value
        elif isinstance(self.value, bytes):
            ret['vd'] = self.value
        elif isinstance(self.value, str):
            ret['vs'] = self.value
        elif self.value is not None:
            ret['v'] = self.numeric(self.value)
        elif self.sum is None:
            raise Exception('Either a sum or a value has to be present in a record.')  # Is this correct?
        return ret


class SenMLDocument(object):
    """A collection of SenMLMeasurement data points"""

    measurement_factory = SenMLMeasurement

    def __init__(self, measurements=None, *args, **kwargs):
        """Constructor"""
        super().__init__(*args, **kwargs)
        if measurements is None:
            measurements = []
        self.measurements = measurements

    @classmethod
    def from_json(cls, json_data):
        """Parse a loaded SenML JSON representation into a SenMLDocument

        @param[in] json_data  JSON list, from json.loads(senmltext)
        """
        base = None
        measurements = []
        version_set = set()
        for record in json_data:
            base = cls.measurement_factory.update_base(base, record, version_set)
            measurement = cls.measurement_factory.from_json(record)
            if measurement is not None:
                measurements.append(measurement.to_absolute(base))

        if len(version_set) > 1:
            raise ValueError(f'Multiple base version detected {version_set}')
        elif len(version_set) == 1:
            version = version_set.pop()
            if version < 10:
                for measurement in measurements:
                    measurement.version = version
            else:  # If version is higher that 10 the measurements are rejected.
                measurements = []

        if len(measurements) > 0:
            ordered_measurements = sorted(measurements, key=lambda x: x.time)
            obj = cls(measurements=ordered_measurements)
        else:
            obj = cls()

        return obj

    def to_json(self):
        """Return a JSON dict"""

        if self.measurements:
            return [item.to_json() for item in self.measurements]
        else:
            return []
