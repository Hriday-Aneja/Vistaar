import asyncio
from app.main import app

THREAD_ID = "db05c3f174f445cb96a859bb1a0617c0"


async def main():
    async with app.router.lifespan_context(app):
        graph = app.state.order_graph

        config = {
            "configurable": {
                "thread_id": THREAD_ID
            }
        }

        snapshot = graph.get_state(config)

        print("Checkpoint found:", snapshot.values != {})
        print("Saved status:", snapshot.values.get("status"))
        print("Saved order IDs:", snapshot.values.get("order_ids"))


asyncio.run(main())