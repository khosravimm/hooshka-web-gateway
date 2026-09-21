from core.governance import RateLimiter


def test_provider_rate_buckets_are_isolated_per_identity_and_provider():
    limiter = RateLimiter()
    limiter.set_rate('chatgpt-web', 2, 2)
    limiter.set_rate('deepseek-web', 1, 1)

    assert limiter.check_rate_limit('user-1', 'chatgpt-web')[0] is True
    assert limiter.check_rate_limit('user-1', 'chatgpt-web')[0] is True
    assert limiter.check_rate_limit('user-1', 'chatgpt-web')[0] is False

    assert limiter.check_rate_limit('user-1', 'deepseek-web')[0] is True
    assert limiter.check_rate_limit('user-1', 'deepseek-web')[0] is False


def test_global_and_provider_buckets_do_not_consume_each_other():
    limiter = RateLimiter()
    limiter._default_rate = 1
    limiter._default_burst = 1
    limiter.set_rate('chatgpt-web', 1, 1)

    assert limiter.check_rate_limit('user-1', 'default')[0] is True
    assert limiter.check_rate_limit('user-1', 'chatgpt-web')[0] is True
