class stdioUI:
    async def prompt(self):
        return await input(">>> ")
        
    def print(self,msg):
        print(msg)