#!/usr/bin/env python
"""bacon -- slice it and dice it!"""

import re
from setuptools import setup, find_packages

# install only bacon, not gammon
packages = [p for p in sorted(find_packages()) if re.match(r"^bacon(\.|$)", p)]

setup(
    name="bacon",
    packages=packages,
    zip_safe=False,
    include_package_data=True,
    install_requires=["networkx>=1.1,<2.0", "pytz"],
    use_scm_version={"version_scheme": "post-release"},
    setup_requires=["setuptools_scm"],
    python_requires=">=3.6",
)
