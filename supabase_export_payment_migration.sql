-- =============================================================================
-- 导出/下载付费闸门（V免签充值额度）
--   1) users 增加 export_credits（剩余导出额度）与 export_pay_exempt（免付费白名单）
--   2) 新建 payment_orders（充值订单）
-- 幂等，可重复执行。Supabase Dashboard -> SQL Editor 粘贴运行。
-- =============================================================================

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS export_credits integer NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS export_pay_exempt boolean NOT NULL DEFAULT false;

CREATE TABLE IF NOT EXISTS payment_orders (
    id            VARCHAR(36)  PRIMARY KEY,
    user_id       VARCHAR(36)  NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    pay_id        VARCHAR(64)  NOT NULL UNIQUE,          -- 我方订单号（V免签 payId）
    vmq_order_id  VARCHAR(64),                           -- V免签订单号
    pay_type      INTEGER      NOT NULL DEFAULT 1,       -- 1=微信 2=支付宝
    price         DOUBLE PRECISION NOT NULL DEFAULT 5.0,
    really_price  DOUBLE PRECISION,                      -- V免签实际应付金额（可能带角分偏移）
    credits       INTEGER      NOT NULL DEFAULT 1,       -- 本单付款成功发放的导出额度
    status        VARCHAR(16)  NOT NULL DEFAULT 'pending',  -- pending / pending_review / paid / expired
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    paid_at       TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_payment_orders_user    ON payment_orders (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_payment_orders_status  ON payment_orders (status);

COMMENT ON COLUMN payment_orders.status IS 'pending | pending_review | paid | expired';
