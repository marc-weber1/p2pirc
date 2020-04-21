from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

class PromptUI:
    def __init__(self):
        self.session = PromptSession()

    async def prompt(self):
        with patch_stdout():
            return await self.session.prompt_async('>>> ') #Try to un-print the thing typed in after
        
    def print(self,msg):
        print(msg)