import json


def parse_to_json(response, write_to_file=False):
    # First script object will always be the json datas
    json_data = response.xpath("/html/body/script[1]/text()").extract_first()
    # Cut off the emoji shit
    json_data = json_data.replace("\\u", "u")
    # Cut off the 'window._sharedData = '
    json_data = json_data[21:]
    # Cut off the ending semicolon
    json_data = json_data[:len(json_data) - 1]

    if write_to_file:
        with open("json_data.txt", "w") as f:
            f.write(json_data)
    json_data = json.loads(json_data)
    assert json_data is not None
    return json_data