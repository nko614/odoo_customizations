from . import models


def _cleanup_null_products(env):
    """Delete old receipt lines with no product (from file-upload era)."""
    env.cr.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'nada_receipt_line')")
    if env.cr.fetchone()[0]:
        env.cr.execute("DELETE FROM nada_receipt_line WHERE product_id IS NULL")


def pre_init_hook(env):
    _cleanup_null_products(env)
