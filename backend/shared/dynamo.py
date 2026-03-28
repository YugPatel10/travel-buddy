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
    scan_forward: bool = True,
    limit: Optional[int] = None,
) -> list[dict]:
    """Query items by partition key with optional sort key prefix.

    Args:
        table_name: DynamoDB table name.
        pk_name: Partition key attribute name (e.g. "PK").
        pk_value: Partition key value to match.
        sk_prefix: Optional sort key prefix filter (begins_with).
        scan_forward: True for ascending SK order, False for descending.
        limit: Maximum number of items to return.
    """
    table = get_table(table_name)
    condition = Key(pk_name).eq(pk_value)
    if sk_prefix:
        condition = condition & Key("SK").begins_with(sk_prefix)

    kwargs: dict[str, Any] = {
        "KeyConditionExpression": condition,
        "ScanIndexForward": scan_forward,
    }
    if limit is not None:
        kwargs["Limit"] = limit

    response = table.query(**kwargs)
    return response.get("Items", [])


def update_item(
    table_name: str,
    key: dict,
    updates: dict,
) -> Optional[dict]:
    """Update specific attributes on an item and return the new version."""
    if not updates:
        return get_item(table_name, key)

    expr_parts: list[str] = []
    attr_names: dict[str, str] = {}
    attr_values: dict[str, Any] = {}

    for i, (field, value) in enumerate(updates.items()):
        placeholder = f"#f{i}"
        val_placeholder = f":v{i}"
        expr_parts.append(f"{placeholder} = {val_placeholder}")
        attr_names[placeholder] = field
        attr_values[val_placeholder] = value

    table = get_table(table_name)
    response = table.update_item(
        Key=key,
        UpdateExpression="SET " + ", ".join(expr_parts),
        ExpressionAttributeNames=attr_names,
        ExpressionAttributeValues=attr_values,
        ReturnValues="ALL_NEW",
    )
    return response.get("Attributes")


def delete_item(table_name: str, key: dict) -> dict:
    """Delete an item by key."""
    table = get_table(table_name)
    return table.delete_item(Key=key)


def batch_write_items(table_name: str, items: list[dict]) -> None:
    """Write multiple items in batches of 25 (DynamoDB batch limit).

    Args:
        table_name: DynamoDB table name.
        items: List of item dicts to put.
    """
    table = get_table(table_name)
    with table.batch_writer() as batch:
        for item in items:
            batch.put_item(Item=item)
