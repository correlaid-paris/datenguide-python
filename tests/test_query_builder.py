import pytest
import re
import sys
import io
import pandas as pd
from datenguidepy import Field, Query


@pytest.fixture
def field_default():
    return Field("WAHL09", args={"year": 2017}, fields=["PART04"], return_type="WAHL09")


@pytest.fixture
def query_default():
    return Query.region(region="09", fields=["BEV001"])


@pytest.fixture
def query_with_enum():
    q = Query.region("09", default_fields=False)
    stat = q.add_field("WAHL09")
    stat.add_field("PART04")
    stat.add_field("year")
    stat.add_field("value")
    return q


@pytest.fixture
def field():
    return Field(
        "WAHL09",
        args={"year": 2017},
        fields=["value", "year", "PART04"],
        default_fields=False,
        return_type="WAHL09",
    )


@pytest.fixture
def query():
    return Query.region(region="09", fields=["BEV001"], default_fields=False)


@pytest.fixture
def all_regions_query(field):
    return Query.all_regions(
        parent="11", fields=["id", "name", field], default_fields=False
    )


@pytest.fixture
def complex_query(field):
    return Query.region(region="09", fields=["id", "name", field], default_fields=False)


@pytest.fixture
def more_complex_query(complex_query):
    query = complex_query
    source = Field("source", fields=["title_de"], return_type="Source")
    statistic2 = Field(
        name="BEV001",
        args={"statistics": "R12612"},
        fields=["value", "year", source],
        default_fields=False,
    )
    query.add_field(statistic2)
    return query


def test_create_query_is_class_query(query):
    assert isinstance(query, Query)


def test_create_query_class_without_start_filed_raises_error():
    with pytest.raises(TypeError):
        Query()


def test_basic_graphql_string(query):
    graphql_query = query.get_graphql_query()
    assert graphql_query[0] == re.sub(
        " +", " ", """{region (id: "09"){BEV001 }}""".replace("\n", " ")
    )


def test_get_fields_to_query():
    field = Field(
        name="WAHL09",
        args={"year": 2017},
        fields=["value", "PART04"],
        default_fields=False,
    )
    subfields_string = field._get_fields_to_query(field)
    assert subfields_string == "WAHL09 (year: 2017){value PART04 }"


def test_get_complex_graphql_string(complex_query):
    graphql_query = complex_query.get_graphql_query()
    assert graphql_query[0] == re.sub(
        "    ",
        "",
        """{
            region (id: "09"){
                id name WAHL09 (year: 2017){value year PART04 }
                }
            }""".replace(
            "\n", ""
        ),
    )


def test_get_complex_graphql_string_without_args():
    field = Field(name="WAHL09", fields=["value"], default_fields=False)
    no_args_query = Query.region(
        region="09", fields=["id", "name", field], default_fields=False
    )

    graphql_query = no_args_query.get_graphql_query()
    assert graphql_query[0] == re.sub(
        "    ",
        "",
        """{
        region (id: "09"){
            id name WAHL09 {value }}
            }""".replace(
            "\n", ""
        ),
    )


def test_get_multiple_stats(more_complex_query):
    graphql_query = more_complex_query.get_graphql_query()
    assert graphql_query[0] == re.sub(
        "    ",
        "",
        """{
        region (id: "09"){
            id name WAHL09 (year: 2017){value year PART04 }
            BEV001 (statistics: R12612){value year source {title_de }}}
        }""".replace(
            "\n", ""
        ),
    )


def test_get_all_fields(query):
    assert query.get_fields() == ["region", "BEV001"]


def test_get_all_fields_complex(more_complex_query):
    assert more_complex_query.get_fields() == [
        "region",
        "id",
        "name",
        "WAHL09",
        "value",
        "year",
        "PART04",
        "BEV001",
        "value",
        "year",
        "source",
        "title_de",
    ]


def test_multiple_filter_args():
    statistic1 = Field(
        name="BETR09",
        args={"FRUNW2": ["FRUART0111", "FRUART0112"]},
        fields=["FRUNW2", "value", "year"],
        default_fields=False,
    )
    multiple_args_query = Query.region(
        region="02", fields=[statistic1], default_fields=False
    )

    graphql_query = multiple_args_query.get_graphql_query()
    assert graphql_query[0] == re.sub(
        "    ",
        "",
        """{
            region (id: "02"){
                BETR09 (FRUNW2: [FRUART0111, FRUART0112]){FRUNW2 value year }
                }
            }""".replace(
            "\n", ""
        ),
    )


def test_all_regions(all_regions_query):
    graphql_query = all_regions_query.get_graphql_query()[0]
    expected_query = re.sub(
        r"\n\s+",
        "",
        """query ($page : Int, $itemsPerPage : Int) {
            allRegions (page: $page, itemsPerPage: $itemsPerPage){
                regions (parent: "11"){
                    id name WAHL09 (year: 2017){
                        value year PART04 }
                }
                page itemsPerPage total }
        }""",
    )
    assert graphql_query == expected_query


def test_nuts(field):
    query = Query.all_regions(
        parent="11", nuts=3, fields=["id", "name", field], default_fields=False
    )
    graphql_query = query.get_graphql_query()[0]
    assert graphql_query == re.sub(
        r"\n\s+",
        "",
        """query ($page : Int, $itemsPerPage : Int) {
            allRegions (page: $page, itemsPerPage: $itemsPerPage){
                regions (parent: "11", nuts: 3){
                    id name WAHL09 (year: 2017){value year PART04 }
                }
                page itemsPerPage total }
        }""",
    )


def test_lau(field):
    query = Query.all_regions(
        parent="11", lau=3, fields=["id", "name", field], default_fields=False
    )
    graphql_query = query.get_graphql_query()[0]
    assert re.sub(" +", " ", graphql_query.replace("\n", " ")) == re.sub(
        r"\n\s+",
        "",
        """query ($page : Int, $itemsPerPage : Int) {
            allRegions (page: $page, itemsPerPage: $itemsPerPage){
                regions (parent: "11", lau: 3){
                    id name WAHL09 (year: 2017){value year PART04 }
                }
                page itemsPerPage total }
        }""",
    )


def test_filter_for_all(query):
    field = Field(
        name="WAHL09",
        args={"year": 2017, "PART04": "ALL"},
        fields=["value", "PART04"],
        default_fields=False,
        return_type="WAHL09",
    )
    query = Query.region(region="09", fields=["id", "name", field])
    graphql_query = query.get_graphql_query()
    assert graphql_query[0] == re.sub(
        "    ",
        "",
        """{
            region (id: "09"){
                id name WAHL09 (
                    year: 2017, filter:{ PART04: { nin: []}}){
                        value PART04 }
                }
        }""".replace(
            "\n", ""
        ),
    )


def test_add_fields_stepwise():
    query = Query.region(region="11", default_fields=False)
    statistic1 = query.add_field("BEV001", default_fields=False)
    statistic1.add_field("year")
    statistic2 = Field(
        name="WAHL09",
        args={"year": 2017, "PART04": "ALL"},
        fields=["value", "PART04"],
        default_fields=False,
        return_type="WAHL09",
    )
    query.add_field(statistic2)

    query2 = Query.region(
        region="11",
        fields=[
            Field(
                name="BEV001",
                fields=["year"],
                default_fields=False,
                return_type="BEV001",
            ),
            Field(
                name="WAHL09",
                args={"year": 2017, "PART04": "ALL"},
                fields=["value", "PART04"],
                default_fields=False,
                return_type="WAHL09",
            ),
        ],
        default_fields=False,
    )
    assert query.get_graphql_query() == query2.get_graphql_query()

    graphql_query = query.get_graphql_query()
    assert graphql_query[0] == re.sub(
        "    ",
        "",
        """{
                region (id: "11"){
                    BEV001 {year }
                    WAHL09 (year: 2017, filter:{ PART04: { nin: []}}){value PART04 }
                }
        }""".replace(
            "\n", ""
        ),
    )


def test_add_fields_all_regions():
    all_reg_query = Query.all_regions(parent="11")
    all_reg_query.add_field("BEV001")

    graphql_query = all_reg_query.get_graphql_query()[0]
    assert graphql_query == re.sub(
        r"\n\s+",
        "",
        """query ($page : Int, $itemsPerPage : Int) {
            allRegions (page: $page, itemsPerPage: $itemsPerPage){
                regions (parent: "11"){
                    id name BEV001 {
                        year value source {title_de valid_from periodicity name url }}
                }
                page itemsPerPage total }
        }""",
    )


def test_add_args_stepwise():
    query = Query.region(region="11")
    statistic1 = query.add_field("BEV001")
    statistic1.add_field("year")
    statistic1.add_args({"year": 2017})

    query2 = Query.region(
        region="11", fields=[Field(name="BEV001", args={"year": 2017}, fields=["year"])]
    )

    assert query.get_graphql_query() == query2.get_graphql_query()


def test_default_fields(query_default):
    graphql_query = query_default.get_graphql_query()
    assert graphql_query[0] == re.sub(
        "    ",
        "",
        """{region (id: "09"){id name BEV001
            {year value source
            {title_de valid_from periodicity name url }}}}""".replace(
            "\n", " "
        ),
    )


def test_get_all_stats_info():
    info = Query.all_regions().get_info()
    assert "name" in info.fields


def test_get_field_info():
    info = Query.all_regions().get_info("BEV001")
    assert "BEVM01" in info.fields


def test_drop_field(query):
    query = query.drop_field("BEV001")
    assert query.get_fields() == ["region"]


def test_drop_field_without_assignment(query):
    query.drop_field("BEV001")
    assert query.get_fields() == ["region"]


def test_drop_field_all_regions(all_regions_query):
    all_regions_query = all_regions_query.drop_field("WAHL09")
    assert all_regions_query.get_fields() == [
        "allRegions",
        "regions",
        "id",
        "name",
        "page",
        "itemsPerPage",
        "total",
    ]


def test_process_query(query_default):
    df = query_default.results()
    assert isinstance(df, pd.DataFrame)


def test_invalid_query(query):
    with pytest.raises(RuntimeError):
        query.results()


def test_process_query_meta(query_default):
    meta_data = query_default.meta_data()
    assert isinstance(meta_data, dict)


def test_invalid_query_meta(query):
    with pytest.raises(RuntimeError):
        query.meta_data()


def test_multiple_regions_query():
    query = Query.region(region=["01", "02"], fields=["BEV001"])
    graphql_query = query.get_graphql_query()
    assert len(graphql_query) == 2, "wrong amount of query strings"
    assert graphql_query[1].startswith(
        '{region (id: "02")'
    ), "not properly iterated over all regions"


@pytest.mark.xfail
def test_arguments_info(query_default):
    stat = query_default.add_field("BEV001")
    info = stat.arguments_info()
    expected_info = """\x1b[4myear\x1b[0m: LIST of type SCALAR(Int)

\x1b[4mstatistics\x1b[0m: LIST of type ENUM(BEV001Statistics)
enum values:
R12612: Statistik der Geburten

\x1b[4mALTMT1\x1b[0m: LIST of type ENUM(ALTMT1)
enum values:
ALT000B20: unter 20 Jahre
ALT020B25: 20 bis unter 25 Jahre
ALT025B30: 25 bis unter 30 Jahre
ALT030B35: 30 bis unter 35 Jahre
ALT035B40: 35 bis unter 40 Jahre
ALT040UM: 40 Jahre und mehr
GESAMT: Gesamt

\x1b[4mBEVM01\x1b[0m: LIST of type ENUM(BEVM01)
enum values:
MONAT01: Januar
MONAT02: Februar
MONAT03: März
MONAT04: April
MONAT05: Mai
MONAT06: Juni
MONAT07: Juli
MONAT08: August
MONAT09: September
MONAT10: Oktober
MONAT11: November
MONAT12: Dezember
GESAMT: Gesamt

\x1b[4mGES\x1b[0m: LIST of type ENUM(GES)
enum values:
GESM: männlich
GESW: weiblich
GESAMT: Gesamt

\x1b[4mLEGIT2\x1b[0m: LIST of type ENUM(LEGIT2)
enum values:
LEGIT01A: Eltern miteinander verheiratet
LEGIT02A: Eltern nicht miteinander verheiratet
GESAMT: Gesamt

\x1b[4mNAT\x1b[0m: LIST of type ENUM(NAT)
enum values:
NATA: Ausländer(innen)
NATD: Deutsche
GESAMT: Gesamt

\x1b[4mfilter\x1b[0m: INPUT_OBJECT(BEV001Filter)"""
    assert info == expected_info


@pytest.mark.xfail
def test_field_info(query_default):
    stat = query_default.add_field("BEV001")
    info = stat.fields_info()
    assert (
        info
        == """id: Interne eindeutige ID
year: Jahr des Stichtages
value: Wert
source: Quellenverweis zur GENESIS Regionaldatenbank
ALTMT1: Altersgruppen der Mutter (unter 20 bis 40 u.m.)
BEVM01: Monat der Geburt
GES: Geschlecht
LEGIT2: Legitimität
NAT: Nationalität"""
    )


def test_enum_info(query_default):
    stat = query_default.add_field("BEV001")
    ges = stat.add_field("GES")
    info = ges.enum_info()
    expected_info = """GESM: männlich
GESW: weiblich
GESAMT: Gesamt"""
    assert info == expected_info


def test_description(query_default):
    stat = query_default.add_field("BEV001")
    descr = stat.description()
    # assert descr == "Lebend Geborene"
    assert descr == "BEV001"


@pytest.mark.xfail
def test_get_info_stat(query_default):
    stringio = io.StringIO()
    sys.stdout = stringio
    stat = query_default.add_field("BEV001")
    stat.get_info()
    info = re.sub(r"\n", "", stringio.getvalue())
    print(info)
    expected_info = re.sub(
        r"\n\s+",
        "",
        """\x1b[1mkind:\x1b[0m
        OBJECT

        \x1b[1mdescription:\x1b[0m
        BEV001

        \x1b[1marguments:\x1b[0m
        \x1b[4myear\x1b[0m: LIST of type SCALAR(Int)

        \x1b[4mstatistics\x1b[0m: LIST of type ENUM(BEV001Statistics)
        enum values:
        R12612: Statistik der Geburten

        \x1b[4mALTMT1\x1b[0m: LIST of type ENUM(ALTMT1)
        enum values:
        ALT000B20: unter 20 Jahre
        ALT020B25: 20 bis unter 25 Jahre
        ALT025B30: 25 bis unter 30 Jahre
        ALT030B35: 30 bis unter 35 Jahre
        ALT035B40: 35 bis unter 40 Jahre
        ALT040UM: 40 Jahre und mehr
        GESAMT: Gesamt

        \x1b[4mBEVM01\x1b[0m: LIST of type ENUM(BEVM01)
        enum values:
        MONAT01: Januar
        MONAT02: Februar
        MONAT03: März
        MONAT04: April
        MONAT05: Mai
        MONAT06: Juni
        MONAT07: Juli
        MONAT08: August
        MONAT09: September
        MONAT10: Oktober
        MONAT11: November
        MONAT12: Dezember
        GESAMT: Gesamt

        \x1b[4mGES\x1b[0m: LIST of type ENUM(GES)
        enum values:
        GESM: männlich
        GESW: weiblich
        GESAMT: Gesamt

        \x1b[4mLEGIT2\x1b[0m: LIST of type ENUM(LEGIT2)
        enum values:
        LEGIT01A: Eltern miteinander verheiratet
        LEGIT02A: Eltern nicht miteinander verheiratet
        GESAMT: Gesamt

        \x1b[4mNAT\x1b[0m: LIST of type ENUM(NAT)
        enum values:
        NATA: Ausländer(innen)
        NATD: Deutsche
        GESAMT: Gesamt

        \x1b[4mfilter\x1b[0m: INPUT_OBJECT(BEV001Filter)

        \x1b[1mfields:\x1b[0m
        id: Interne eindeutige ID
        year: Jahr des Stichtages
        value: Wert
        source: Quellenverweis zur GENESIS Regionaldatenbank
        ALTMT1: Altersgruppen der Mutter (unter 20 bis 40 u.m.)
        BEVM01: Monat der Geburt
        GES: Geschlecht
        LEGIT2: Legitimität
        NAT: Nationalität

        \x1b[1menum values:\x1b[0m
        None""",
    )
    assert info == expected_info


def test_get_fields_with_return_type(field, query_with_enum):
    fields_and_types = field._get_fields_with_types()
    expected_fields_and_types = set(
        [
            ("WAHL09", "WAHL09"),
            ("value", "Float"),
            ("year", "Int"),
            ("PART04", "PART04"),
        ]
    )
    assert set(fields_and_types) == expected_fields_and_types

    fields_and_types = query_with_enum._get_fields_with_types()
    expected_fields_and_types = set(
        [
            ("WAHL09", "WAHL09"),
            ("region", "Region"),
            ("value", "Float"),
            ("year", "Int"),
            ("PART04", "PART04"),
        ]
    )
    assert set(fields_and_types) == expected_fields_and_types
