// Elora Store - Supabase Configuration

const SUPABASE_URL = "https://dmttevcncsxzbamazmmq.supabase.co";

const SUPABASE_PUBLISHABLE_KEY = "sb_publishable_UxXOA92gcX3CHzbU7h3udQ_3khfMMzH";

const { createClient } = supabase;

const eloraSupabase = createClient(
  SUPABASE_URL,
  SUPABASE_PUBLISHABLE_KEY
);
