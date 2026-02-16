def calculate_delta(current, previous):
    if previous == 0: return None
    return (current - previous) / previous
