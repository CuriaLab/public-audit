# Public Audit
This repo is intended for external parties to validate the logic and calculation of different products and metrics.


## Requirements
  - Python 3.13
  - Poetry (ideally installed within a venv)


## Installation
  1. Clone the repository:
    git clone [[repository-url]]
    cd public-audit
  
  2. Install dependencies
    poetry update
  
  3. Deploy FastAPI:
    poetry run uvicorn main:app 



## Usage
  After deploying FastAPI, the url in which the instance will be hosted at
  will be shown within the terminal.
    - By default, this will be hosted at (http://127.0.0.1:8000)

  You can access the API by simply using cURL or copy-pasting the URL + desired
  endpoint and DAO within Postman or a browser.
  
### Get raw data
"{fast_api_url}/{dao}/data/raw"


### Get formatted data
"{fast_api_url}/{dao}/data/format"


### Get forum score
"{fast_api_url}/{dao}/metrics/forum_score"


## License
This project is licensed under the MIT License - see the LICENSE file for details


## Security
Please report any security issues or vulnerabilities by creating an issue in the repository.
