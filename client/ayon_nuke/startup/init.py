from ayon_core.pipeline import install_host
from ayon_nuke.api import NukeHost

# Attempt to register host.
try:
    host = NukeHost()
    install_host(host)

# Current environment might not be 100% fully AYON compatible.
# e.g. on farm, using Deadline or RoyalRender native Nuke plugin.
# If an incomplete AYON environment is provided, the host
# will not be able to install.
# We still allow Nuke to start as-is, might be enough for rendering.
# Otherwise it'll raise on AYON dependency with more meaningful error.
except Exception as error:
    print(
        f"Cannot initialize AYON Nuke host: {error}. "
        "This might result in unexpected results."
    )
