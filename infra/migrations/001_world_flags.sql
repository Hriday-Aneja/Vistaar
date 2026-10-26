-- For a PostgreSQL database that already exists (new databases get these columns automatically).
-- Every distributor and calendar row that exists before this migration came from the demo seed.
ALTER TABLE distributors ADD COLUMN IF NOT EXISTS is_demo boolean NOT NULL DEFAULT false;
ALTER TABLE distributors ADD COLUMN IF NOT EXISTS added_by_shop_id integer REFERENCES shops(id);
ALTER TABLE event_calendar ADD COLUMN IF NOT EXISTS is_demo boolean NOT NULL DEFAULT false;
UPDATE distributors SET is_demo = true WHERE added_by_shop_id IS NULL;
UPDATE event_calendar SET is_demo = true;