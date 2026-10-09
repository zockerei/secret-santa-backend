from app.draw import find_assignment


def check_valid(user_ids, assignment, forbidden=None):
    forbidden = forbidden or {}
    assert set(assignment) == set(user_ids), "everybody gives a gift"
    assert sorted(assignment.values()) == sorted(user_ids), "everybody receives exactly one gift"
    for gifter, recipient in assignment.items():
        assert gifter != recipient
        assert recipient not in forbidden.get(gifter, set())


def test_everybody_gives_and_receives_once():
    user_ids = list(range(1, 11))
    for _ in range(100):
        check_valid(user_ids, find_assignment(user_ids, {}))


def test_two_people_give_to_each_other():
    assert find_assignment([1, 2], {}) == {1: 2, 2: 1}


def test_forbidden_recipients_are_avoided():
    user_ids = [1, 2, 3, 4, 5]
    forbidden = {1: {2, 3}, 2: {3, 4}, 3: {4, 5}, 4: {5, 1}, 5: {1, 2}}
    for _ in range(100):
        check_valid(user_ids, find_assignment(user_ids, forbidden), forbidden)


def test_impossible_returns_none():
    assert find_assignment([1, 2], {1: {2}}) is None
    assert find_assignment([1, 2, 3], {1: {2, 3}}) is None


def test_needs_two_people():
    assert find_assignment([], {}) is None
    assert find_assignment([1], {}) is None


def test_result_is_random():
    user_ids = list(range(1, 8))
    results = {tuple(sorted(find_assignment(user_ids, {}).items())) for _ in range(50)}
    assert len(results) > 1
