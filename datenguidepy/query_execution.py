from typing import Dict, Any, cast, Optional, NamedTuple, List, Tuple, Union
import requests
import re

Json_Dict = Dict[str, Any]
Json_List = List[Json_Dict]
Json = Union[Json_Dict, Json_List]

StatMeta = Dict[str, str]
EnumMeta = Dict[str, Dict[Optional[str], str]]
QueryResultsMeta = Dict[str, Union[StatMeta, EnumMeta]]


class ExecutionResults(NamedTuple):
    """Results of a query with the results itself and the according meta data.
    """

    query_results: Json_List
    meta_data: QueryResultsMeta


class TypeMetaData(NamedTuple):
    """The meta data of a field, which consist of the kind, fields and enum values.
    """

    kind: str
    fields: Optional[Json_Dict]
    enum_values: Optional[Dict[str, str]]


class FieldMetaDict(dict):
    """[description]
    """

    def get_return_type(self) -> str:
        """Returns the return type of the field of the FieldMetaDict.

        :return: The return type of the field.
        :rtype: str
        """
        if self["type"]["kind"] == "LIST":
            return self["type"]["ofType"]["name"]
        else:
            return self["type"]["name"]

    def get_arguments(self) -> Dict[str, Tuple[Optional[str], ...]]:
        """[summary]

        :return: [description]
        :rtype: Dict[str, Tuple[Optional[str], ...]]
        """

        def get_type_of(
            argument: Dict[str, Any]
        ) -> Tuple[Optional[str], Optional[str]]:
            if argument["type"]["ofType"]:
                return (
                    argument["type"]["ofType"]["kind"],
                    argument["type"]["ofType"]["name"],
                )
            else:
                return None, None

        return {
            cast(str, arg["name"]): (
                cast(Optional[str], arg.get("type", {}).get("kind", {})),
                cast(Optional[str], arg.get("type", {}).get("name")),
                *get_type_of(arg),
            )
            for arg in self["args"]
        }


class GraphQlMetaDataProvider(object):
    endpoint: str = "https://api-next.datengui.de/graphql"

    REQUEST_HEADER: Dict[str, str] = {"Content-Type": "application/json"}

    _META_DATA_CACHE: Json_Dict = dict()

    _meta_type_info: str = """
        query TypeInfo($type: String!) {
          __type(name: $type) {
            kind
            enumValues {
              name
              description
            }
            fields {
              name
              type {
                ofType {
                  name
                }
                kind
                name
                description
              }
              description
              args {
                name
                type {
                  kind
                  name
                  ofType {
                    name
                    description
                    kind
                  }
                }
              }
            }
          }
        }
    """

    def __init__(self, endpoint=None):
        if endpoint is not None:
            self.endpoint = endpoint

    def get_query_stat_meta(
        self, query_fields_with_types: List[Tuple[str, str]]
    ) -> StatMeta:
        # Region type contains all the statistics fields
        query_fields = [
            field_with_type[0] for field_with_type in query_fields_with_types
        ]
        stat_descriptions = self.get_stat_descriptions()
        if stat_descriptions is not None:
            stat_meta = {
                stat: stat_descriptions[stat][0]
                for stat in stat_descriptions
                if stat in query_fields
            }
        else:
            stat_meta = {"error": "STAT META DATA COULD NOT BE LOADED"}
            # wrong casting as the result is a list of Json
        return stat_meta

    def get_query_enum_meta(
        self, query_fields_with_types: List[Tuple[str, str]]
    ) -> EnumMeta:
        enum_meta: EnumMeta = {}
        for field, field_type in query_fields_with_types:
            type_info = self.get_type_info(field_type)
            if type_info is None:
                enum_meta[field] = {"error": "ENUM META DATA COULD NOT BE LOADED"}
            if cast(TypeMetaData, type_info).kind == "ENUM":
                enum_meta[field] = cast(
                    Dict[Optional[str], str], cast(TypeMetaData, type_info).enum_values
                )
        return enum_meta

    def get_type_info(
        self, graph_ql_type: str, verbose=False
    ) -> Optional[TypeMetaData]:
        """Returns a json which at top level is a dict with all the
        fields of the type

        :param graph_ql_type: [description]
        :type graph_ql_type: str
        :param verbose: [description], defaults to False
        :type verbose: bool, optional
        :return: [description]
        :rtype: Optional[TypeMetaData]
        """

        if graph_ql_type in self.__class__._META_DATA_CACHE:
            if verbose:
                print("use cache")
            return self.__class__._META_DATA_CACHE[graph_ql_type]
        variables = {"type": graph_ql_type}
        query_json: Json_Dict = {}
        query_json["query"] = self._meta_type_info
        query_json["variables"] = variables
        if verbose:
            print("query REST API")
        info = self._send_request(query_json)
        if info:
            type_kind = info["data"]["__type"]["kind"]

            if type_kind == "OBJECT":
                field_meta: Optional[Json_Dict] = {
                    f["name"]: FieldMetaDict(f)
                    for f in info["data"]["__type"]["fields"]
                }
            else:
                field_meta = None

            if type_kind == "ENUM":
                enum_vals: Optional[Dict[str, str]] = {
                    value["name"]: value["description"]
                    for value in info["data"]["__type"]["enumValues"]
                }
            else:
                enum_vals = None
            type_meta = TypeMetaData(type_kind, field_meta, enum_vals)
            self.__class__._META_DATA_CACHE[graph_ql_type] = type_meta
            return type_meta
        else:
            return None

    @staticmethod
    def _process_stat_meta_data(type_fields: Json_Dict) -> List[Json_Dict]:
        return [
            type_fields[name]
            for name in type_fields
            if "statistics" in type_fields[name].get_arguments()
        ]

    @staticmethod
    def _extract_main_description(description: str) -> str:
        match = re.match(r"^\s*\*\*([^*]*)\*\*", description)
        if match:
            return match.group(1)
        else:
            return "NO DESCRIPTION FOUND"

    def get_stat_descriptions(self) -> Dict[str, Tuple[str, str]]:
        """[summary]

        :return: [description]
        :rtype: [type]
        """
        stat_meta = self.get_type_info("Region")
        if stat_meta:
            stat_descriptions = self._create_stat_desc_dic(
                # casting given "Regions" type
                cast(Json_Dict, cast(TypeMetaData, stat_meta).fields)
            )
            return stat_descriptions
        else:
            raise RuntimeError("Meta data provider was anable to fetch statistics")

    def is_statistic(self, stat_candidate: str) -> bool:
        return stat_candidate in self.get_stat_descriptions()

    @staticmethod
    def _create_stat_desc_dic(raw_response: Json_Dict) -> Dict[str, Tuple[str, str]]:
        return dict(
            (
                field["name"],
                (
                    GraphQlMetaDataProvider._extract_main_description(
                        field["description"]
                    ),
                    field["description"],
                ),
            )
            for field in GraphQlMetaDataProvider._process_stat_meta_data(raw_response)
        )

    def _send_request(self, query_json: Json_Dict) -> Optional[Json_Dict]:
        resp = requests.post(
            self.endpoint, headers=self.REQUEST_HEADER, json=query_json
        )
        if resp.status_code == 200:
            return resp.json()
        else:
            print(self.endpoint)
            print(f"No result, got HTML status code {resp.status_code}")
            return None


class SchemaJsonMetaDataProvider(object):
    def get_query_stat_meta(
        self, query_fields_with_types: List[Tuple[str, str]]
    ) -> StatMeta:
        pass

    def is_statistic(self, stat_candidate: str) -> bool:
        return stat_candidate in self.get_stat_descriptions()
        pass

    def get_stat_descriptions(self) -> Dict[str, Tuple[str, str]]:
        pass

    def get_type_info(
        self, graph_ql_type: str, verbose=False
    ) -> Optional[TypeMetaData]:
        pass


class QueryExecutioner(object):
    """Queries the Datenguide API for data and meta data.

    :param alternative_endpoint: [description], defaults to None
    :type alternative_endpoint: Optional[str], optional
    :return: [description]
    :rtype: None
    """

    REQUEST_HEADER: Dict[str, str] = {"Content-Type": "application/json"}
    endpoint: str = "https://api-next.datengui.de/graphql"

    def __init__(
        self, alternative_endpoint: Optional[str] = None, meta_data_provider=None
    ) -> None:
        if alternative_endpoint:
            self.endpoint = cast(str, alternative_endpoint)

        if meta_data_provider is None:
            self.meta_data_provider = GraphQlMetaDataProvider(self.endpoint)
        else:
            meta_data_provider = meta_data_provider

    def get_type_info(
        self, graph_ql_type: str, verbose=False
    ) -> Optional[TypeMetaData]:
        """Returns a json which at top level is a dict with all the
        fields of the type

        :param graph_ql_type: [description]
        :type graph_ql_type: str
        :param verbose: [description], defaults to False
        :type verbose: bool, optional
        :return: [description]
        :rtype: Optional[TypeMetaData]
        """
        return self.meta_data_provider.get_type_info(graph_ql_type, verbose)

    @staticmethod
    def _pagination_json(page: int) -> Json_Dict:
        return {"page": page, "itemsPerPage": 1000}

    def run_query(self, query) -> Optional[List[ExecutionResults]]:
        """[summary]

        :param query: [description]
        :type query: [type]
        :return: [description]
        :rtype: Optional[List[ExecutionResults]]
        """
        all_results = [
            self._run_single_query_json(query_json, query._get_fields_with_types())
            for query_json in self._generate_post_json(query)
        ]
        if not any(map(lambda r: r is None, all_results)):
            return [cast(ExecutionResults, r) for r in all_results]
        else:
            return None

    def _run_single_query_json(
        self, query_json: Json_Dict, query_fields_with_types: List[Tuple[str, str]]
    ) -> Optional[ExecutionResults]:
        if "allRegions" in [
            field_with_types[0] for field_with_types in query_fields_with_types
        ]:
            results = []
            page = 0
            while True:
                query_json["variables"] = self._pagination_json(page)
                result_page = self._send_request(query_json)
                if result_page is None:
                    return None
                results.append(result_page)
                if (cast(Json_Dict, result_page)["data"]["allRegions"]["page"] + 1) * (
                    cast(Json_Dict, result_page)["data"]["allRegions"]["itemsPerPage"]
                ) >= cast(Json_Dict, result_page)["data"]["allRegions"]["total"]:
                    break
                else:
                    page += 1
        else:
            single_result = self._send_request(query_json)
            if single_result is None:
                return None
            else:
                results = [single_result]

        if results:
            meta: QueryResultsMeta = dict()
            meta
            meta["statistics"] = self.meta_data_provider.get_query_stat_meta(
                query_fields_with_types
            )
            meta["enums"] = self.meta_data_provider.get_query_enum_meta(
                query_fields_with_types
            )
            return ExecutionResults(
                query_results=cast(Json_List, results), meta_data=meta
            )
        else:
            return None

    @staticmethod
    def _generate_post_json(query) -> List[Dict[str, str]]:
        jsons: List[Dict[str, str]] = []
        for query_string in query.get_graphql_query():
            post_json: Json_Dict = dict()
            post_json["query"] = query_string
            jsons.append(post_json)
        return jsons

    def _send_request(self, query_json: Json_Dict) -> Optional[Json_Dict]:
        resp = requests.post(
            self.endpoint, headers=self.REQUEST_HEADER, json=query_json
        )
        if resp.status_code == 200:
            return resp.json()
        else:
            print(self.endpoint)
            print(f"No result, got HTML status code {resp.status_code}")
            return None
