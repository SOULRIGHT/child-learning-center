"""growth_teacher_interpretation_v2 Structured Outputs JSON Schema."""

OUTPUT_SCHEMA_VERSION = 'growth_teacher_interpretation_v2'
OUTPUT_SCHEMA_NAME = 'growth_teacher_interpretation_v2'

_TEXT_EVIDENCE = {
    'type': 'object',
    'additionalProperties': False,
    'required': ['text', 'evidence_ids'],
    'properties': {
        'text': {'type': 'string'},
        'evidence_ids': {
            'type': 'array',
            'minItems': 1,
            'items': {'type': 'string'},
        },
    },
}

_ACTION = {
    'type': 'object',
    'additionalProperties': False,
    'required': ['text', 'evidence_ids', 'conditional'],
    'properties': {
        'text': {'type': 'string'},
        'evidence_ids': {
            'type': 'array',
            'minItems': 1,
            'items': {'type': 'string'},
        },
        'conditional': {'type': 'boolean'},
    },
}

INTERPRETATION_JSON_SCHEMA = {
    'type': 'object',
    'additionalProperties': False,
    'required': [
        'schema_version',
        'priority_insight',
        'interpretation',
        'observations',
        'next_actions',
        'next_check',
    ],
    'properties': {
        'schema_version': {
            'type': 'string',
            'enum': [OUTPUT_SCHEMA_VERSION],
        },
        'priority_insight': _TEXT_EVIDENCE,
        'interpretation': _TEXT_EVIDENCE,
        'observations': {
            'type': 'array',
            'maxItems': 3,
            'items': _TEXT_EVIDENCE,
        },
        'next_actions': {
            'type': 'array',
            'maxItems': 2,
            'items': _ACTION,
        },
        'next_check': _TEXT_EVIDENCE,
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
