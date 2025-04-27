# -*- coding: utf-8 -*-
"""
This Python script creates offline copies of the VW manuals
available at https://userguide.volkswagen.de

https://github.com/gromk/vw-offline-manual-creator
"""

import requests, os, __main__, sys, re, shutil, logging, datetime
from pathlib import Path
from bs4 import BeautifulSoup as bs

script_path = Path(__main__.__file__).parent

# Initialize the logger
log_file = Path(__main__.__file__).with_suffix('.log')
logging.shutdown()
log_handlers = [logging.FileHandler(log_file, mode='w'), logging.StreamHandler()]
logging.basicConfig(level=logging.INFO, format='%(message)s', handlers=log_handlers)



# =============================================================================
# USER-DEFINED PARAMETERS
# =============================================================================

# Vehicule ID number
# => it can be either :
#    - your VIN number (17 characters)
#    - a UK registration plate (if your VIN number does not work, search for
#      an equivalent vehicle ID on e.g. https://www.gumtree.com/)
vehicle_id = "<enter-your-id-here>"

# Language of the user guide
# => the list of available languages for the above vehicle can be found by running
#    the script once and then checking the contents of j3['availableLanguages']
lang = "fr_FR"

# Output folder
# => a subfolder will then be created for each created manual
output_folder = script_path/"manuals"

# Collapse/expand behavior of the offline manual (by default: 'one')
# => if extend_mode='all', the contents are always visible, from the
#    beginning to the end of the manual
# => if extend_mode='single', all the chapters are hidden, with exception
#    of the selected one
# => if extend_mode='toggle', all the chapters are hidden by default,
#    and then can be toggled individually (several chapters can then be 
#    visible at the same time)
extend_mode = 'single'

# Indicate where to display the treeview containing the table of contents
# => toc_position='sidebar' (default) => left of the page
# => toc_position='header' => top of the page (only two levels of nodes)
# => toc_position='none' => no treeview
toc_position = 'sidebar'

# Crash when encoutering a 404 error ?
# => if crash_on_error=True, the manual will not be created whenever a section
#    fails to download (some sections are not available sometimes, so you will
#    have to try again later)
# => if crash_on_error=False, sections that could not be downloaded will appear
#    blank in the offline manual
crash_on_error = False


# =============================================================================
# FUNCTION DEFINITIONS
# =============================================================================

# Replicate the DOM structure of the original online manual (see the
# joint HTML templates) and populate it with the content downloaded
# from https://userguide.volkswagen.de
#
# => technically, it is a recursive function which browses the tree structure
#    returned by VW API, building :
#     - a string containing the HTML for the body of the manual
#     - a string containing the HTML for the table of contents
#     - a Python dictionary containing the values for 'href' attributes of all links
def build_dom(topic, session, templates, crash_on_error, level=0) :
    logging.info(f"  ...processing chapter '{topic['label']}'...")

    if len(topic['children']) > 0 :   
        
        # Recursive calls to build_dom in order to build children nodes
        html_body_children = ""
        html_toc_children = ""
        html_href_children = {}
        for child in topic['children'] :
            body_child, toc_child, href_child = build_dom(child, session, templates, crash_on_error, level+1)
            html_body_children += body_child
            html_toc_children += toc_child
            html_href_children.update(href_child)
               
        # Replace the placeholders in the HTML templates
        repl = {
                    'TOPIC_ID':       topic['nodeId'],
                    'TOPIC_TITLE':    topic["label"],
                    'TOPIC_CHILDREN': html_body_children,
                    'TOC_CHILDREN':   html_toc_children
                }
        html_body = replace_in_template(templates['topic_w_children'], repl)
        html_href = html_href_children
        if toc_position == 'header' and level > 0 :
            repl['TOPIC_LINK'] = 'title'+topic['nodeId']
            html_toc = replace_in_template(templates['toc_wo_children'], repl)
        else :
            html_toc  = replace_in_template(templates['toc_w_children'], repl)
        
    else :
        
        # The content of this topic must be loaded with another HTTP request
        content = ""
        html_href = {}
        if topic['linkTarget'] != "" :
            try :
                r = session.get(f"https://userguide.volkswagen.de{legacy_str}/api/web/V6/topic?key={topic['linkTarget']}&displaytype=topic&language={lang}&query=undefined")
                r.raise_for_status()
                rj = r.json()
                content = rj['bodyHtml']
                if '</html>' in content :
                    content = re.match(r'<html[^>]*>(.*)</html>', content, re.DOTALL).group(1)
                html_href = rj['linkState']
                
            except requests.exceptions.HTTPError as e :
                if crash_on_error :
                    logging.error(e)
                    sys.exit(1)
                content = "<div></div>"
                logging.warning(e)
                
        # Replace the placeholders in the HTML templates
        repl = {
                    'TOPIC_ID':       topic['nodeId'],
                    'TOPIC_LINK':     topic['linkTarget'],
                    'TOPIC_TITLE':    topic["label"],
                    'TOPIC_CONTENT':  content
                }
        html_body = replace_in_template(templates['topic_wo_children'], repl)
        html_toc = replace_in_template(templates['toc_wo_children'], repl)
        
    return (html_body, html_toc, html_href)


# Replace template placeholders with their actual values
# => template_str is the string containing the HTML template
#    (with placeholders in the {{MUSTACHE}} format)
# => dict_replace is a dictionary : {placeholder: value}
# => returns a new string
def replace_in_template(template_str, dict_replace) :
    for k,v in dict_replace.items() :
        template_str = template_str.replace('{{'+k+'}}', v)
    return template_str


# Download the file located at <url> and store it inside <local_filename>
# => if the operation fails, a message is displayed and execution continues
def download_file(session, url, local_filename) :
    try :
        with session.get(url, stream=True) as r :
            r.raise_for_status()
            logging.info(f"Downloading {url}...")
            local_filename.parent.mkdir(parents=True, exist_ok=True)
            with open(local_filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192) : 
                    f.write(chunk)
    except requests.exceptions.HTTPError as e :
        logging.warning(e)



# =============================================================================
# LOOKUP FOR THE AVAILABLE ONLINE MANUALS
# =============================================================================

# Retrieve the VIN number from the registration plate
vehicle_id = vehicle_id.upper()
if len(vehicle_id) != 17 :
    r1 = requests.get(f"https://www.volkswagen.co.uk/api/vrm-lookup/0.4/vrm/lookup/{vehicle_id}")
    j1 = r1.json()
    if not j1['error'] is None :
        logging.error(j1['error'])
        logging.error(f"The registration plate {vehicle_id} was not found in the database")
        sys.exit(2)
    vin = j1['vehicleDetails']['vin']
else :
    if not vehicle_id.startswith("WVGZZZ") :
        logging.error("The VIN number MUST start with WVGZZZ (Volkswagen brand)")
        sys.exit(3)
    vin = vehicle_id

# Create a persistent session which will be used for the API calls
http_session = requests.Session()

# Create the JSESSIONID cookie and associate it with the VIN number
r2 = http_session.post(f"https://userguide.volkswagen.de/public/vin/login/{lang}",
                            data=f'vin={vin}',
                            headers={
                                'Content-Type': 'application/x-www-form-urlencoded',
                                'Content-Length': '21'
                            })

# Check if 'legacy' must be appended to the base url
legacy_mode = ('legacy' in r2.url)
legacy_str = '/legacy' if legacy_mode else ''

# Request for the list of available manuals
r3 = http_session.get(f"https://userguide.volkswagen.de{legacy_str}/api/web/V6/search?query=&facetfilters=topic-type_|_welcome&lang={lang}&page=0&pageSize=20")
j3 = r3.json()

manuals = j3['results']
if len(manuals) == 0 :
    logging.error('No manual found. Please try with another vehicle ID.')
    sys.exit(4)

# Let the user choose the manuel that he wants to download
print("The following online manuals were found:")
for i, manual in enumerate(manuals) :
    print(f"   [{i+1}] {manual['title']}")
choice = ''
while not choice.isdigit() or int(choice) == 0 or int(choice) > len(manuals) :
    choice = input("Choice: ")
manual = manuals[int(choice)-1]

# Subfolder where the user guide will be created
sanitized_title = re.sub(r"['’(), ]", "_", manual["title"])
subfolder = output_folder/f"{vehicle_id}_{sanitized_title}"
if subfolder.is_dir() :
    shutil.rmtree(subfolder)
    while True :
        try :
            if not subfolder.is_dir() :
                break
        except PermissionError :
            pass
subfolder.mkdir(parents=True, exist_ok=True)


# =============================================================================
# CREATE THE DOCUMENT DOM STRUCTURE AND FILL IT TOPIC BY TOPIC
# =============================================================================

logging.info("\nThe user guide download will start now.\n")
logging.info(f"   => download time : {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
logging.info(f"   => vehicle VIN   : {vin}")
logging.info(f"   => manual title  : {manual['title']}\n")

# Language-dependant strings
r = http_session.get(f"https://userguide.volkswagen.de{legacy_str}/w/{lang}/welcome/")
strings = dict(re.findall(r'strings\["([a-zA-Z0-9.]+)"]\s*=\s*"([^"]+)";', r.text))

# Templates of the webpage, containing several {{PLACEHOLDERS}}
templates = {}
for k in ['index', 'topic_w_children', 'topic_wo_children', 'toc_w_children', 'toc_wo_children'] :
    templates[k] = (script_path/"templates"/f"{k}.html").read_text()

# Load the tree structure of the user guide (JSON + DOM)
r4 = http_session.get(f"https://userguide.volkswagen.de{legacy_str}/api/web/V6/topic?key={manual['topicId']}&displaytype=topic&language={lang}&query=undefined")
j4 = r4.json()
ug_json = j4['trees'][0]['children']
ug_soup = bs(j4['abstractText'], 'lxml')

# Concatenate the sections of the user guide
body_content = ""
toc_content = ""
href_content = {}
for topic in ug_json :
    body, toc, href = build_dom(topic, http_session, templates, crash_on_error)
    body_content += body
    toc_content += toc
    href_content.update(href)

# Populate the main HTML template
html = replace_in_template(templates['index'],
                           {
                               'LANG_CODE':         lang,
                               'VEHICLE_MODEL':     ug_soup.find('span', {'data-class': 'vw-modell-bez'}).text,
                               'VEHICLE_VIN':       vin,
                               'TOC_TITLE':         strings['tab.directory'],
                               'TOC_CONTENT':       toc_content,
                               'USERGUIDE_ID':      manual['topicId'],
                               'USERGUIDE_TITLE':   manual["title"],
                               'USERGUIDE_DATE':    ug_soup.find('span', {'data-class': 'vw-modell-variante'}).text,
                               'USERGUIDE_CONTENT': body_content,
                               'OPEN_ONLINE'      : strings['label.open.web'],
                               'EXTEND_MODE'      : extend_mode
                           })


                  
# =============================================================================
# DOM MODIFICATIONS TO MAKE THE OFFLINE VERSION FULLY FUNCTIONAL
# =============================================================================

logging.info("\nSource code is being adapted to make the offline version fully functional...\n")

soup = bs(html, 'lxml')

# Tweak the position of the table of contents
# (nothing to do if toc_position=='sidebar')
if toc_position != 'sidebar' :
    
    # Enlarge the body part of the manual
    soup.select_one('#resultList')['class'] = re.sub(r'col-md-[0-9]+', 'col-md-12', ' '.join(soup.select_one('#resultList')['class']))
    
    if toc_position == 'none' :
        # Hide the treeview
        soup.select_one('#sideBar')['class'] += ['mobileSidebar']  
        
    elif toc_position == 'header' :
        # Make the treeview appear at the top of the page
        sidebar = soup.select_one('#sideBar')
        classes = ' '.join(sidebar['class'])
        classes = re.sub(r'col-md-[0-9]+', 'col-md-6', classes)
        classes = re.sub(r'cssSticky', '', classes)
        classes += ' col-md-offset-3'
        sidebar['class'] = classes
        sidebar['style'] = re.sub(r'top:\s*[0-9]+px\s*;?', '', sidebar['style'])
        # Remove the vertical scrollbar
        soup.select_one('#contentTable')['style'] = re.sub(r'overflow-y:\sscroll\s*;?', '', soup.select_one('#contentTable')['style'])
        # Let the treeview take all the vertical space it needs
        soup.select_one('#tabs_sidebar')['style'] = re.sub(r'max-height:\s*[0-9]+px\s*;?', '', soup.select_one('#tabs_sidebar')['style'])
        soup.select_one('#contentTable')['style'] = re.sub(r'max-height:\s*[0-9]+px\s*;?', '', soup.select_one('#contentTable')['style'])
        # Expand only the first level of nodes in the treeview
        for div in soup.select('ul.tree > li.toc_entry > .contentTable__panel.w_children') :
            div['class'] += ['selected']

# In 'all' mode, expand all the nodes of the manual (using 'selected' class name)
# (unlike 'toggle' and 'single', chapters won't expand/collapse)
if extend_mode == 'all' :
    for elt in soup.select('div[id^="title"].tttitle, div.ttchildren') :
        elt['class'] += ['selected']

# Update the attributes of all the links...
#   'toggle' or 'single' => 'data-goto' will be used by Javascript to create a click handler
#   'all' => 'href' scrolls the browser to a given DOM element (without Javascript)
#
# ...links pointing to a figure
if extend_mode != 'all' :
    for a in soup.select('a[href^="#"]') :
        a['data-goto'] = a['href'][1:]
        a['href'] = '#'
# ...links pointing to another topic
for a in soup.select('a.dynamic-link') :
    if extend_mode == 'all' :
        a['href'] = '#'
        if a['id'] in href_content :
            if not href_content[a['id']]['target'] is None :
                a['href'] += href_content[a['id']]['target']
    else :
        a['href'] = '#'
        a['data-goto'] = href_content[a['id']]['target']
    del a.attrs['checked-link']
    del a.attrs['data-facets']

# All HTML tags in the contents of tooltip boxes must be removed
for span in soup.select('span[data-toggle="popover"]') :
    tooltip_soup = bs(span['data-content'], 'lxml')
    span['data-content'] = tooltip_soup.get_text()
    


# =============================================================================
# DOWNLOAD THE CSS FILES LINKED TO THE ONLINE WEBPAGE
# =============================================================================

logging.info("\nCreating main.css and print.css based on the online CSS files.\n")

html = str(soup)

r5 = http_session.get(f"https://userguide.volkswagen.de{legacy_str}/w/{lang}/")
webpage = bs(r5.text, 'lxml')

css_screen = ""
css_print = ""

css_resources = {}

for link in webpage.findAll('link') :
    if link['rel'][0].lower() == "stylesheet" :
        url = f"https://userguide.volkswagen.de{link['href']}"
        css_online_dir, css_filename = url.rsplit('/', maxsplit=1)
        
        logging.info(f"  ...processing online stylesheet '{css_filename}'...")
        
        r6 = http_session.get(url)
        r6.encoding = "utf-8"  # encoding must be enforced because the headers do not give any indication
        if r6.status_code == requests.codes.ok :
            css_text = r6.text
        else :
            logging.error(f'An error {r6.status_code} occurred while downloading "{css_filename}"')
            sys.exit(5)
        
        if link.get('media', 'screen') == 'print' :
            css_print += css_text+'\n\n'
        else :
            css_screen += css_text+'\n\n'
        
        # Detect all the external urls in this CSS for subsequent download
        for rel_path in re.findall(r"url\(([^()]+)\)", css_text) :
            if not rel_path.startswith('data:') :
                if '#' in rel_path :
                    rel_path = rel_path.rsplit('#', maxsplit=1)[0]
                if '?' in rel_path :
                    rel_path = rel_path.rsplit('?', maxsplit=1)[0]
                css_resources[rel_path] = css_online_dir+'/'+rel_path
                
# The CSS files are now written to disk
(subfolder/"main.css").write_text(css_screen, encoding="utf-8")
(subfolder/"print.css").write_text(css_print, encoding="utf-8")



# =============================================================================
# DOWNLOAD ALL THE IMAGES/FONTS FOUND IN THE HTML DOCUMENT AND THE CSS FILES
# =============================================================================

logging.info("\nDownloading the page resources (images, fonts). This can take a few minutes...\n")

# Images in the HTML body
for img in soup.findAll('img') :
    if img['data-src'].startswith('https:'):
        url = img['data-src']
    else:
        url = f"https://userguide.volkswagen.de{legacy_str}{img['data-src']}"
    filename = url.split('key=')[1]
    local_path = subfolder/"img"/filename
    if not local_path.is_file() :
        download_file(http_session, url, local_path)
        
    # Update the 'src' attribute so that it points to the local file
    img['src'] = "img/"+filename

# Resources found in the CSS files
for rel_path, url in css_resources.items() :
    local_path = subfolder/rel_path
    if not local_path.is_file() :
        download_file(http_session, url, local_path)
             
# Also copy the logo which is displayed while the manual is loading
shutil.copy(script_path/"repo_logo.svg", subfolder/"img"/"repo_logo.svg")
        

# =============================================================================
# FINALLY DUMP THE PAGE CONTENT IN index.html
# =============================================================================

logging.info(f"\nThe offline manual has been succesfully created in '{subfolder.resolve()}'\n")
(subfolder/"index.html").write_text(str(soup), encoding="utf8")

logging.shutdown()
