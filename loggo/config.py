"""
Python default access settings
"""

FACILITY = 'loggo'
PORT = 999
DO_PRINT = True
DO_WRITE = True
COLOUR = False
IP = '0.0.0.0'

SETTINGS = dict(facility=FACILITY,
                port=PORT,
                do_print=DO_PRINT,
                do_write=DO_WRITE,
                ip=IP,
                colour=COLOUR)

LOG_LEVELS = dict(critical='CRITICAL',
                  dev='ERROR',
                  minor='WARNING',
                  info='INFO',
                  debug='DEBUG')


try:
    from colorama import init
    init()
    from colorama import Fore, Back, Style
    COLOUR_MAP = dict(red=Fore.RED + Style.BRIGHT,
                      green=Fore.GREEN + Style.BRIGHT,
                      critical=Fore.WHITE + Back.RED + Style.BRIGHT,
                      dev=Fore.RED + Style.BRIGHT,
                      debug=Style.DIM,
                      greendim=Style.DIM+Fore.GREEN,
                      end=Style.RESET_ALL)
except ImportError:
    COLOUR_MAP = dict()
