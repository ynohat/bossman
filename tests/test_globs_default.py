import pytest
from bossman.plugins.akamai.property import PropertyResource
from bossman import get_resources


@pytest.fixture(scope="module")
def resources():
    resources = list()
    resources.append(PropertyResource("dist/akamai/cloudlets/ER_bossman_demo", name="ER_bossman_demo"))
    resources.append(PropertyResource("dist/akamai/property/www-dev", name="www-dev"))
    resources.append(PropertyResource("dist/akamai/property/www-integration", name="www-integration"))
    resources.append(PropertyResource("dist/akamai/property/www-prod", name="www-prod"))
    return resources

@pytest.mark.parametrize(
    "glob, expected_result",
    (
        (["*"], ["ER_bossman_demo", "www-dev", "www-integration", "www-prod"]),
        (["www"], ["www-dev", "www-integration", "www-prod"]),
    ),
)

def test_glob_default(resources, glob, expected_result):
    result = get_resources(resources, glob, False)
    assert(len(result) == len(expected_result))
    for r in result:
        assert(r.name in expected_result)
