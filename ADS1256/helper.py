import datetime

# Helper function to handle leap years
def is_leap_year(year):
    if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
        return True
    return False

# Days in each month for non-leap years and leap years
days_in_month_non_leap = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
days_in_month_leap = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

def epoch_to_datetime(epoch_time):
    # Remove the 27 seconds added to account for UTC leap seconds
    epoch_time -= 27

    # Calculate the number of seconds in a day
    seconds_in_day = 86400
    days_since_epoch = epoch_time // seconds_in_day  # Integer division to get the number of full days
    remaining_seconds = epoch_time % seconds_in_day  # Remaining seconds in the current day

    # Calculate the year starting from 1970
    year = 1970
    days_in_year = 365 if not is_leap_year(year) else 366

    # Loop through years until we reach the correct one
    while days_since_epoch >= days_in_year:
        days_since_epoch -= days_in_year
        year += 1
        days_in_year = 365 if not is_leap_year(year) else 366

    # Now days_since_epoch is the day of the year
    # Calculate the month and day
    days_in_month = days_in_month_leap if is_leap_year(year) else days_in_month_non_leap
    month = 0
    while days_since_epoch >= days_in_month[month]:
        days_since_epoch -= days_in_month[month]
        month += 1

    # Now days_since_epoch is the day of the month
    day = days_since_epoch + 1  # Day is 1-indexed

    # Calculate hours, minutes, and seconds from the remaining seconds in the day
    hours = remaining_seconds // 3600
    remaining_seconds %= 3600
    minutes = remaining_seconds // 60
    seconds = remaining_seconds % 60

    # Return the result as a datetime structure
    return datetime.datetime(year, month + 1, day, hours, minutes, seconds)

if __name__ == "__main__":
    # Example usage:
    epoch_time = 1623934800  # Example epoch time (seconds since 1970)
    dt = epoch_to_datetime(epoch_time)
    print(dt)  # Output should be a datetime object representing the date and time
