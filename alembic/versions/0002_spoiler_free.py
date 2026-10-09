"""spoiler free

Simplifies the schema so an admin can take part without seeing who gives to whom:
- receivers becomes participants. The pair moves from the recipient's row (gifter_id)
  to the gifter's own row (recipient_id), so a user only ever needs their own row.
- events gets a free text name (the event_names table goes) and drawn_at instead of status.
- emails are stored lowercase and the timestamps get a time zone.
- the duplicated indexes and the check constraints that added nothing are dropped.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-09 18:00:00

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # users
    op.execute("""
        DROP INDEX IF EXISTS idx_user_created_at, idx_user_email, idx_user_is_admin,
            ix_users_created_at, ix_users_is_admin
    """)
    op.execute("""
        ALTER TABLE users
            DROP CONSTRAINT IF EXISTS check_user_email_format,
            DROP CONSTRAINT IF EXISTS check_user_email_min_length,
            DROP CONSTRAINT IF EXISTS check_user_name_not_empty,
            DROP CONSTRAINT IF EXISTS check_password_hash_length,
            ALTER COLUMN name TYPE varchar(50),
            ALTER COLUMN email TYPE varchar(255),
            ALTER COLUMN created_at TYPE timestamptz USING created_at AT TIME ZONE 'UTC'
    """)
    op.execute("UPDATE users SET email = lower(trim(email))")

    # events: free text name, drawn_at instead of status
    op.execute("""
        DROP INDEX IF EXISTS idx_event_created_at, idx_event_date_status, idx_event_name_status,
            idx_event_status, ix_events_created_at, ix_events_date, ix_events_event_name,
            ix_events_status
    """)
    op.execute("""
        ALTER TABLE events
            ADD COLUMN name varchar(100),
            ADD COLUMN drawn_at timestamptz,
            ALTER COLUMN created_at TYPE timestamptz USING created_at AT TIME ZONE 'UTC'
    """)
    op.execute("UPDATE events SET name = event_name")
    # The real draw time is unknown, every event with pairs counts as drawn when it was created
    op.execute("""
        UPDATE events e SET drawn_at = e.created_at
        WHERE EXISTS (SELECT 1 FROM receivers r WHERE r.event_id = e.id AND r.gifter_id IS NOT NULL)
    """)
    op.execute("ALTER TABLE events ALTER COLUMN name SET NOT NULL")
    op.execute("ALTER TABLE events DROP COLUMN event_name, DROP COLUMN status")
    op.execute("DROP TABLE event_names")
    op.execute("DROP TYPE IF EXISTS eventstatus")

    # receivers -> participants, with the pair on the gifter's row
    op.execute("""
        CREATE TEMPORARY TABLE old_pairs ON COMMIT DROP AS
        SELECT event_id, gifter_id, user_id AS recipient_id FROM receivers WHERE gifter_id IS NOT NULL
    """)
    op.execute("""
        DROP INDEX IF EXISTS idx_receiver_event_gifter, idx_receiver_event_message_null,
            idx_receiver_event_user, idx_receiver_gifter, idx_receiver_user_message,
            ix_receivers_gifter_id
    """)
    op.execute("""
        ALTER TABLE receivers
            DROP CONSTRAINT IF EXISTS check_event_id_positive,
            DROP CONSTRAINT IF EXISTS check_gifter_id_positive_or_null,
            DROP CONSTRAINT IF EXISTS check_no_self_assignment,
            DROP CONSTRAINT IF EXISTS check_user_id_positive,
            DROP CONSTRAINT IF EXISTS receivers_event_id_fkey,
            DROP CONSTRAINT IF EXISTS receivers_user_id_fkey,
            DROP CONSTRAINT IF EXISTS receivers_gifter_id_fkey,
            DROP COLUMN gifter_id,
            ADD COLUMN recipient_id integer
    """)
    op.execute("ALTER TABLE receivers RENAME TO participants")
    op.execute("ALTER TABLE participants RENAME CONSTRAINT receivers_pkey TO participants_pkey")
    # A gifter has to be a participant to have a row for the pair, so no past pair is lost
    op.execute("""
        INSERT INTO participants (event_id, user_id)
        SELECT DISTINCT o.event_id, o.gifter_id FROM old_pairs o
        WHERE NOT EXISTS (
            SELECT 1 FROM participants p WHERE p.event_id = o.event_id AND p.user_id = o.gifter_id
        )
    """)
    op.execute("""
        UPDATE participants p SET recipient_id = o.recipient_id
        FROM old_pairs o
        WHERE o.event_id = p.event_id AND o.gifter_id = p.user_id
    """)
    op.execute("""
        ALTER TABLE participants
            ADD CONSTRAINT participants_user_id_fkey
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            ADD CONSTRAINT participants_event_id_fkey
                FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE,
            ADD CONSTRAINT participants_recipient_id_fkey
                FOREIGN KEY (recipient_id) REFERENCES users (id) ON DELETE SET NULL,
            ADD CONSTRAINT uq_participants_event_recipient UNIQUE (event_id, recipient_id),
            ADD CONSTRAINT ck_participants_not_self CHECK (recipient_id <> user_id)
    """)
    op.execute("CREATE INDEX ix_participants_user_id ON participants (user_id)")


def downgrade() -> None:
    """Downgrade schema."""
    raise NotImplementedError("There is no way back to the old schema, restore a backup instead")
