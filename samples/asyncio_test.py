import asyncio

async def fetch(name, sec):
    print(f"{name} start")
    await asyncio.sleep(sec)
    print(f"{name} end")
    return f"{name} done"

async def stream():
    for i in range(3):
        await asyncio.sleep(0.3)
        yield f"chunk-{i}"

async def main():
    # 并发执行两个任务
    r1, r2 = await asyncio.gather(fetch("A", 1), fetch("B", 1))
    print(r1, r2)

    async for chunk in stream():
        print("got:", chunk)

asyncio.run(main())