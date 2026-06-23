"""Quick API smoke against Compose nginx (run inside backend container)."""

from __future__ import annotations

import asyncio
import os

import httpx

BASE = os.environ.get("SMOKE_API_BASE", "http://nginx/api/v1")
PASSWORD = os.environ.get("SMOKE_PASSWORD", "FilumTest123!")


async def login(client: httpx.AsyncClient, email: str) -> str:
  response = await client.post(f"{BASE}/auth/login", json={"email": email, "password": PASSWORD})
  response.raise_for_status()
  return response.json()["access_token"]


async def main() -> None:
  async with httpx.AsyncClient(timeout=30.0) as client:
    manager_token = await login(client, "demo.video.copy.lead@example.com")
    headers = {"Authorization": f"Bearer {manager_token}"}

    flags = await client.get(f"{BASE}/workflow-graph/feature-flags", headers=headers)
    flags.raise_for_status()
    print("feature-flags:", flags.json())

    task_center = await client.get(f"{BASE}/task-center", headers=headers)
    task_center.raise_for_status()
    snapshot = task_center.json()
    print(
      "task-center inbox:",
      len(snapshot.get("inbox", {}).get("items", [])),
      "tracking:",
      len(snapshot.get("tracking", {}).get("items", [])),
    )

    templates = await client.get(f"{BASE}/workflow-graph/templates", headers=headers)
    templates.raise_for_status()
    template_list = templates.json()
    print("templates:", [item.get("code") for item in template_list])

    editor_token = await login(client, "demo.video.copy.a@example.com")
    editor_headers = {"Authorization": f"Bearer {editor_token}"}
    editor_center = await client.get(f"{BASE}/task-center", headers=editor_headers)
    editor_center.raise_for_status()
    editor_snapshot = editor_center.json()
    inbox_titles = [item.get("title") for item in editor_snapshot.get("inbox", {}).get("items", [])[:5]]
    print("editor inbox sample:", inbox_titles)

    batch_template = next(
      (item for item in template_list if item.get("code") == "topic_meeting_batch_v1"),
      None,
    )
    if batch_template:
      instances = await client.get(
        f"{BASE}/workflow-graph/templates/{batch_template['id']}/instances",
        headers=headers,
        params={"limit": 3},
      )
      instances.raise_for_status()
      instance_list = instances.json()
      print("batch instances:", len(instance_list))
      if instance_list:
        children = await client.get(
          f"{BASE}/workflow-graph/instances/{instance_list[0]['id']}/children",
          headers=headers,
        )
        children.raise_for_status()
        child_list = children.json()
        if child_list:
          node_instances = child_list[0].get("node_instances") or []
          task_ids = [node.get("task_id") for node in node_instances if node.get("task_id")]
          print("first child task_ids:", task_ids[:3])
          print("first child current_node_key:", child_list[0].get("current_node_key"))

    print("API smoke: OK")


if __name__ == "__main__":
  asyncio.run(main())
