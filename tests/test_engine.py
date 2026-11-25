from archsim.engine import Simulation


def test_actions_run_in_time_order():
    sim = Simulation()
    log = []
    sim.schedule(3, lambda: log.append("c"))
    sim.schedule(1, lambda: log.append("a"))
    sim.schedule(2, lambda: log.append("b"))
    sim.run(until=10)
    assert log == ["a", "b", "c"]
    assert sim.now == 10


def test_ties_run_in_scheduling_order():
    sim = Simulation()
    log = []
    for name in "xyz":
        sim.schedule(1, lambda n=name: log.append(n))
    sim.run(until=1)
    assert log == ["x", "y", "z"]


def test_actions_after_horizon_do_not_run():
    sim = Simulation()
    log = []
    sim.schedule(5, lambda: log.append("late"))
    sim.run(until=4)
    assert log == []


def test_actions_can_schedule_more_actions():
    sim = Simulation()
    times = []

    def tick():
        times.append(sim.now)
        sim.schedule(1, tick)

    sim.schedule(0, tick)
    sim.run(until=3)
    assert times == [0, 1, 2, 3]
