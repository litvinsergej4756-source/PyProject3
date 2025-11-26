#The function prints to the console instructions on how to use the command line to run the script.
@staticmethod
def print_help():
    help_message = """
        📚 Command Line Usage
        1.  python MainController.py mode=1 count=<NUMBER>
            Example: python MainController.py mode=1 count=5

        2.  python MainController.py mode=0 pid=<PRODUCT_ID>
            Example: python MainController.py mode=0 pid=1234

        3.  python MainController.py -h
            python MainController.py --help
            python MainController.py h=1
        """
    print(help_message)