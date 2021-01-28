<!-- PROJECT LOGO -->
<br />
<p align="center">
  <a href="https://github.com/gromk/vw-offline-manual-creator">
    <img src="repo_logo.png" alt="Logo" width="160" height="120">
  </a>

  <h3 align="center">vw-offline-manual-creator</h3>

  <p align="center">
Create offline copies of the VW car manuals
available at https://userguide.volkswagen.de
    <br />
    <br />
    <a href="https://gromk.github.io/vw-offline-manual-creator-demo/">View Demo</a>
  </p>
</p>


<!-- ABOUT THE PROJECT -->
## About The Project

If you are the owner of a Volkswagen car, you may find its manual online at https://userguide.volkswagen.de/. However, no direct download option is offered and in-browser "save to..." solutions do not achieve good results (not even with dedicated extensions).

This project provides a tool to create local copies of your car manuals, that you can host on your smartphone, tablet or NAS. You will then be able to read them anywhere, anytime, even if Volkswagen stops maintaining its online service.

The Python script scraps the manual contents by sending HTTP requests to Volkswagen servers. It then builds the offline document by filling HTML templates (included in the repo) which were adapted from the online version. **The tool is fully functional as of January 2021. Like any web-scraper, some bugs may appear over time should the online service get updated.**


<!-- GETTING STARTED -->
## Getting Started

### Prerequisites

Your will need to have Python 3.6+ installed, with the [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/bs4/doc/) module.

Two common strategies to achieve that:
* Download and use the [Python 3.x installer](https://www.python.org/) built for your platform (Windows, Linux, MacOS...), then use ``pip`` (Python's official package installer) to get Beautiful Soup:
  ```sh
  pip install beautifulsoup4
  ```
* Install [Anaconda](https://www.anaconda.com) distribution for your platform, then use the built-in package manager to get Beautiful Soup:
  ```sh
  conda install bs4
  ```

### Installation
To get a local copy up and running, either:
* clone this directory with ```git clone https://github.com/gromk/vw-offline-manual-creator```
* or just download ``vw-offline-manual-creator.py``, ``repo_logo.svg`` and the ``templates`` folder to your computer


<!-- USAGE EXAMPLES -->
## Usage

1. Edit the parameters available at the top of ``vw-offline-manual-creator.py`` (see the description below).
2. Run the script with:
  ```sh
  python3 vw-offline-manual-creator.py
  ```


<!-- USER-DEFINED PARAMTERS -->
## Parameters

* ``vehicle_id`` (string) is the VIN number of your vehicle (17 characters, starting with "VWG").

   If your VIN number is not recognized, you can alternatively set the value of ``vehicle_id`` to a UK registration plate. You should easily find a UK vehicle matching yours (model, date...) on [Gumtree](https://www.gumtree.com/), for instance.
   
* ``lang`` (string) defines the language of the manual. Common codes are ``fr_FR`` (French), ``en_GB`` (English), ``de_DE`` (German) or ``es_ES`` (Spanish). You can print ``j3['availableLanguages']`` after dry-running the Python script in order to see the full list of available codes.

* ``output_folder`` (Path) defines where the offline manual will be located. By default, a folder named ``manuals`` will be created in the same dir as the Python script.

  The results will eventually be placed in a subfolder containing the VIN number and the manual title. **This destination subfolder will be overwritten every time that the script is run.**
  
* ``extend_mode`` (string) defines the extend/collapse behavior of the manual chapters. This parameter can take the three following values:
  * ``'single'`` (default)
    Chapters of the manual are expanded/collapsed by clicking on their title bar. Only one chapter is displayed at a time: expanding an item will collapse the previous one. This is the same behavior as the online manual.
    
  * ``'toggle'``
    This is like ``'single'``, except that you can expand several chapters at the same time.
    
  * ``'all'``
    All the chapters of the manual are always expanded. Clicking on the title bar will not collapse the associated chapter. This is the recommended value for printing purposes.
    
* ``toc_position`` (string) defines the position of the table of contents. This parameter can take the three following values:
  * ``'sidebar'`` (default)
    The treeview is displayed at the left of the page. It remains fixed when the page is scrolled up and down. Initially, all the nodes are collapsed. This is the same behavior as the online manual.
    
  * ``'header'``
    The table of contents is located at the top of the page. It contains only two levels of nodes, which are initially extended. The manual takes the full width of the page.
    
  * ``'none'``
    No table of contents is displayed. The manual takes the full width of the page.
    
* ``crash_on_error`` (boolean) indicates whether or not the script execution must be stopped whenever a HTTP error is encounted while requesting for the content of a chapter. If set to ``false`` (default), some chapters may be missing in the resulting offline manual, because of server-side temporary problems (try again some days later if this is the case). If set to ``true``, the script will crash if it is not able to download the manual in full.


<!-- LICENSE -->
## License

Distributed under the MIT License. See `LICENSE` for more information.
