import pytest
from bossman.plugins.akamai.property import PropertyResource
from bossman import get_resources


@pytest.fixture(scope="module")
def resources():
    resources = list()
    resources.append(PropertyResource("dist/akamai/property/global.mydomain.com", name="global.mydomain.com"))
    resources.append(PropertyResource("dist/akamai/property/testglobal.mydomain.com", name="testglobal.mydomain.com"))
    resources.append(PropertyResource("dist/akamai/property/logistics.mydomain.com", name="logistics.mydomain.com"))
    resources.append(PropertyResource("dist/akamai/property/logistics.mydomain.com-related-domains", name="logistics.mydomain.com-related-domains"))
    return resources

@pytest.mark.parametrize(
    "glob, expected_result",
    (
        (["*"], ["global.mydomain.com", "testglobal.mydomain.com", "logistics.mydomain.com", "logistics.mydomain.com-related-domains"]),
        (["*/logistics.mydomain.com*"], ["logistics.mydomain.com", "logistics.mydomain.com-related-domains"]),
        (["*/logistics.mydomain.com*"], ["logistics.mydomain.com", "logistics.mydomain.com-related-domains"]),
        (["*/logistics.mydomain.com"], ["logistics.mydomain.com"]),
        (["dist/akamai/property/logistics.mydomain.com"], ["logistics.mydomain.com"]),
        (["*global.mydomain.com"], ["global.mydomain.com", "testglobal.mydomain.com"]),
        (["*/global.mydomain.com"], ["global.mydomain.com"]),
    ),
)

def test_glob_exact_match(resources, glob, expected_result):
    result = get_resources(resources, glob, True)
    assert(len(result) == len(expected_result))
    for r in result:
        assert(r.name in expected_result)
