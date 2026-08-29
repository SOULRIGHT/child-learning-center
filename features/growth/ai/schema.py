"""growth_teacher_interpretation_v1 Structured Outputs JSON Schema."""

OUTPUT_SCHEMA_VERSION = 'growth_teacher_interpretation_v1'
OUTPUT_SCHEMA_NAME = 'growth_teacher_interpretation_v1'

_TEXT_EVIDENCE = {
    'type': 'object',
    'additionalProperties': False,
    'required': ['text', 'evidence_ids'],
    'properties': {
        'text': {'type': 'string'},
        'evidence_ids': {
            'type': 'array',
            'items': {'type': 'string'},
        },
    },
}

_SUGGESTION = {
    'type': 'object',
    'additionalProperties': False,
    'required': ['text', 'evidence_ids', 'conditional'],
    'properties': {
        'text': {'type': 'string'},
        'evidence_ids': {
            'type': 'array',
            'items': {'type': 'string'},
        },
        'conditional': {'type': 'boolean'},
    },
}

INTERPRETATION_JSON_SCHEMA = {
    'type': 'object',
    'additionalProperties': False,
    'required': ['schema_version', 'summary', 'observations', 'suggestions'],
    'properties': {
        'schema_version': {
            'type': 'string',
            'enum': [OUTPUT_SCHEMA_VERSION],
        },
        'summary': _TEXT_EVIDENCE,
        'observations': {
            'type': 'array',
            'maxItems': 3,
            'items': _TEXT_EVIDENCE,
        },
        'suggestions': {
            'type': 'array',
            'maxItems': 2,
            'items': _SUGGESTION,
        },
    },
}


def structured_output_format():
    """Responses API text.format payload. official json_schema Structured Outputs."""
    return {
        'type': 'json_schema',
        'name': OUTPUT_SCHEMA_NAME,
        'strict': True,
        'schema': INTERPRETATION_JSON_SCHEMA,
    }
