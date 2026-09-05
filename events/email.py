from accounts.email import send_email


def send_registration_confirmed_email(*, registration):
    event = registration.event
    subject = f"Registration confirmed: {event.title}"
    text_content = (
        f"You are registered for {event.title} at {event.date_time}. "
        f"Location: {event.location}."
    )
    send_email(
        to_email=registration.user.email,
        subject=subject,
        text_content=text_content,
    )


def send_registration_cancelled_email(*, registration):
    event = registration.event
    subject = f"Registration cancelled: {event.title}"
    text_content = (
        f"Your registration for {event.title} has been cancelled. "
        "Your spot is no longer reserved."
    )
    send_email(
        to_email=registration.user.email,
        subject=subject,
        text_content=text_content,
    )


def send_waitlist_joined_email(*, waitlist_entry):
    event = waitlist_entry.event
    subject = f"You joined the waitlist: {event.title}"
    text_content = (
        f"You are on the waitlist for {event.title}. "
        f"Your current position is {waitlist_entry.position}."
    )
    send_email(
        to_email=waitlist_entry.user.email,
        subject=subject,
        text_content=text_content,
    )


def send_waitlist_cancelled_email(*, waitlist_entry):
    event = waitlist_entry.event
    subject = f"Waitlist cancelled: {event.title}"
    text_content = f"You have left the waitlist for {event.title}."
    send_email(
        to_email=waitlist_entry.user.email,
        subject=subject,
        text_content=text_content,
    )


def send_waitlist_promoted_email(*, registration):
    event = registration.event
    subject = f"You got a spot: {event.title}"
    text_content = (
        f"A spot opened up for {event.title}, and you have been registered automatically. "
        f"Location: {event.location}. Date/time: {event.date_time}."
    )
    send_email(
        to_email=registration.user.email,
        subject=subject,
        text_content=text_content,
    )
