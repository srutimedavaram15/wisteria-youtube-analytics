import pytest

CATEGORY_MAP = {
    '1':  'Film & Animation',
    '2':  'Autos & Vehicles',
    '10': 'Music',
    '15': 'Pets & Animals',
    '17': 'Sports',
    '19': 'Travel & Events',
    '20': 'Gaming',
    '22': 'People & Blogs',
    '23': 'Comedy',
    '24': 'Entertainment',
    '25': 'News & Politics',
    '26': 'Howto & Style',
    '27': 'Education',
    '28': 'Science & Technology',
    '29': 'Nonprofits & Activism',
}


def category_name(category_id: str) -> str:
    return CATEGORY_MAP.get(category_id, 'Other')


@pytest.mark.parametrize("cat_id,expected", [
    ('20', 'Gaming'),
    ('24', 'Entertainment'),
    ('22', 'People & Blogs'),
    ('10', 'Music'),
    ('28', 'Science & Technology'),
    ('1',  'Film & Animation'),
    ('29', 'Nonprofits & Activism'),
])
def test_known_ids_map_correctly(cat_id, expected):
    assert category_name(cat_id) == expected


@pytest.mark.parametrize("cat_id", ['0', '99', '999', '', 'unknown', 'gaming'])
def test_unknown_ids_fall_back_to_other(cat_id):
    assert category_name(cat_id) == 'Other'


def test_all_mapped_ids_are_non_empty():
    for cat_id in CATEGORY_MAP:
        assert category_name(cat_id) != 'Other'
        assert category_name(cat_id) != ''
