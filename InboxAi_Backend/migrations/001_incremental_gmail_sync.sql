ALTER TABLE public.emails
    ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE public.emails
    ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'Pending';

UPDATE public.emails
SET status = 'Pending'
WHERE status IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS emails_gmail_account_message_uidx
    ON public.emails (gmail_account_id, gmail_message_id);
