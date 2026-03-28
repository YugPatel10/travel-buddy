"""DynamoDB helper utilities."""

from __future__ import annotations

from typing import Any, Optional

import boto3
from boto3.dynamodb.conditions import Key


def get_table(table_name: str) -> Any:
    """Return a DynamoDB Table resource."""
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(table_name)


def put_item(table_name: str, item: dict) -> dict:
    """Put an item into a DynamoDB table."""
    table = get_table(table_name)
    return table.put_item(Item=item)


def get_item(table_name: str, key: dict) -> Optional[dict]:
    """Get a single item by key."""
    table = get_table(table_name)
    response = table.get_item(Key=key)
    return response.get("Item")


def query_items(
    table_name: str,
    pk_name: str,
    pk_value: str,
    sk_prefix: Optional[str] = None,
) -> list[dict]:
    """Query items by partition key with optional sort key prefix."""
    table = get_table(table_name)
    condition = Key(pk_name).eq(pk_value)
    if sk_prefix:
        condition = condition & Key("SK").begins_with(sk_prefix)
    response = table.query(KeyConditionExpression=condition)
    return response.get("Items", [])


def delete_item(table_name: str, key: dict) -> dict:
    """Delete an item by key."""
    table = get_table(table_name)
    return table.delete_item(Key=key)
