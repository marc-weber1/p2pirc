from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
import asyncio
import time

async def thing():
    session = PromptSession()
    while True:
        with patch_stdout():
            result = await session.prompt_async('Say something: ')
        print('You said: %s' % result)


    '''while True:
        thing()
        print('123')
        time.sleep(1)'''

async def main():
    asyncio.ensure_future(thing())
    for x in range(10):
        print('Done', x+1)
        await asyncio.sleep(1)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
