"""reading_analysis_output_v1 Structured Outputs JSON Schema."""

OUTPUT_SCHEMA_VERSION = 'reading_analysis_output_v1'
OUTPUT_SCHEMA_NAME = 'reading_analysis_output_v1'
ALLOWED_STATUSES = ('major', 'limited')
ALLOWED_DIMENSIONS = ('expression', 'content')

_EVIDENCE_REF = {
    'type': 'object',
    'additionalProperties': False,
    'required': ['record_id', 'date', 'book_title'],
    'properties': {
        'record_id': {'type': 'integer'},
        'date': {'type': 'string'},
        'book_title': {'type': ['string', 'null']},
    },
}

_OBSERVATION = {
    'type': 'object',
    'additionalProperties': False,
    'required': ['dimension', 'observation', 'evidence_refs'],
    'properties': {
        'dimension': {'type': 'string', 'enum': list(ALLOWED_DIMENSIONS)},
        'observation': {'type': 'string'},
        'evidence_refs': {
            'type': 'array',
            'minItems': 1,
            'maxItems': 4,
            'items': _EVIDENCE_REF,
        },
    },
}

ANALYSIS_JSON_SCHEMA = {
    'type': 'object',
    'additionalProperties': False,
    'required': ['schema_version', 'status', 'observations', 'limitations'],
    'properties': {
        'schema_version': {
            'type': 'string',
            'enum': [OUTPUT_SCHEMA_VERSION],
        },
        'status': {
            'type': 'string',
            'enum': list(ALLOWED_STATUSES),
        },
        'observations': {
            'type': 'array',
            'maxItems': 4,
            'items': _OBSERVATION,
        },
        'limitations': {
            'type': 'array',
            'maxItems': 4,
            'items': {'type': 'string'},
        },
    },
}


def structured_output_format():
    return {
        'type': 'json_schema',
        'name': OUTPUT_SCHEMA_NAME,
        'strict': True,
        'schema': ANALYSIS_JSON_SCHEMA,
    }
