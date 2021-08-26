import logging
import sys
from server import import_plugins

__version__ = "0.16.7"


display_version = "cellxgene v" + __version__

try:
    import_plugins("lol.lol.plugins")
except Exception as e:
    # Make sure to exit in this case, as the lol may not be configured as expected.
    logging.critical(f"Error in import_plugins: {str(e)}")
    sys.exit(1)
