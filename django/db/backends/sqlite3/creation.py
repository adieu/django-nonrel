# SQLite doesn't actually support most of these types, but it "does the right
# thing" given more verbose field definitions, so leave them as is so that
# schema inspection is more useful.
DATA_TYPES = {
    'AutoField':                    'integer',
    'BooleanField':                 'bool',
    'CharField':                    'varchar(%(max_length)s)',
    'CommaSeparatedIntegerField':   'varchar(%(max_length)s)',
    'DateField':                    'date',
    'DateTimeField':                'datetime',
    'DecimalField':                 'decimal',
    'FileField':                    'varchar(100)',
    'FilePathField':                'varchar(100)',
    'FloatField':                   'real',
    'ImageField':                   'varchar(100)',
    'IntegerField':                 'integer',
    'IPAddressField':               'char(15)',
    'NullBooleanField':             'bool',
    'OneToOneField':                'integer',
    'PhoneNumberField':             'varchar(20)',
    'PositiveIntegerField':         'integer unsigned',
    'PositiveSmallIntegerField':    'smallint unsigned',
    'SlugField':                    'varchar(%(max_length)s)',
    'SmallIntegerField':            'smallint',
    'TextField':                    'text',
    'TimeField':                    'time',
    'USStateField':                 'varchar(2)',
}
