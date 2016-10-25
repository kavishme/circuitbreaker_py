from functools import wraps
from datetime import datetime, timedelta

STATE_CLOSED = 'closed'
STATE_OPEN = 'open'
STATE_HALF_OPEN = 'half_open'


class CircuitBreaker(object):
    def __init__(self, expected_exception=Exception, failure_threshold=5, recover_timeout=30, name=None):
        self._expected_exception = expected_exception
        self._failure_count = 0
        self._failure_threshold = failure_threshold
        self._recover_timeout = recover_timeout
        self._state = STATE_CLOSED
        self._opened = datetime.utcnow()
        self._name = name

    def __call__(self, wrapped):
        """
        Applies the circuit breaker decorator to a function
        """
        if self._name is None:
            self._name = wrapped.__name__

        CircuitBreakerMonitor.register(self)

        @wraps(wrapped)
        def wrapper(*args, **kwargs):
            return self.call(wrapped, *args, **kwargs)

        return wrapper

    def call(self, func, *args, **kwargs):
        """
        Calls the decorated function and applies the circuit breaker rules on success or failure
        :param func: Decorated function
        """
        if not self.__is_closed():
            raise CircuitBreakerError(self)
        try:
            result = func(*args, **kwargs)
        except self._expected_exception:
            self.__failure()
            raise

        self.__success()
        return result

    def __is_closed(self):
        """
        Check if state is CLOSED
        Set state to HALF_OPEN and allow the next execution, if recovery timeout has been reached
        """
        if self._state == STATE_OPEN and self.open_remaining <= 0:
            self._state = STATE_HALF_OPEN
            return True

        return self._state == STATE_CLOSED

    def __success(self):
        """
        Close circuit after successful execution
        """
        self.close()

    def __failure(self):
        """
        Count failure and open circuit, if threshold has been reached
        """
        self._failure_count += 1
        if self._failure_count >= self._failure_threshold:
            self.open()

    def open(self):
        """
        Open the circuit breaker
        """
        self._state = STATE_OPEN
        self._opened = datetime.utcnow()

    def close(self):
        """
        Close the circuit breaker
        """
        self._state = STATE_CLOSED
        self._failure_count = 0

    @property
    def open_until(self):
        """
        The datetime, when the circuit breaker will try to recover
        :return: datetime
        """
        return self._opened + timedelta(seconds=self._recover_timeout)

    @property
    def open_remaining(self):
        """
        Number of seconds (int) remaining, the circuit breaker stays in OPEN state
        :return: int
        """
        return (self.open_until - datetime.utcnow()).total_seconds()

    @property
    def failure_count(self):
        return self._failure_count

    @property
    def closed(self):
        return self._state is not STATE_OPEN

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    def __str__(self, *args, **kwargs):
        return self._name


class CircuitBreakerError(Exception):
    def __init__(self, circuit_breaker, *args, **kwargs):
        """
        :param circuit_breaker:
        :param args:
        :param kwargs:
        :return:
        """
        super().__init__(*args, **kwargs)
        self._circuit_breaker = circuit_breaker

    def __str__(self, *args, **kwargs):
        return 'CIRCUIT "%s" OPEN until %s (%d failures, %d sec remaining)' % (
            self._circuit_breaker.name,
            self._circuiit_breaker.open_until,
            self._circuit_breaker.failure_count,
            round(self._circuit_breaker.open_remaining)
        )


class CircuitBreakerMonitor(object):
    circuit_breakers = {}

    @classmethod
    def register(cls, circuit_breaker):
        cls.circuit_breakers[circuit_breaker.name] = circuit_breaker

    @classmethod
    def all_closed(cls):
        if list(cls.get_open()):
            return False
        return True

    @classmethod
    def get_circuits(cls):
        return cls.circuit_breakers.values()

    @classmethod
    def get(cls, name):
        return cls.circuit_breakers.get(name)

    @classmethod
    def get_open(cls):
        for circuit in cls.get_circuits():
            if circuit.state is STATE_OPEN:
                yield circuit

    @classmethod
    def get_closed(cls):
        for circuit in cls.get_circuits():
            if circuit.state is not STATE_OPEN:
                yield circuit