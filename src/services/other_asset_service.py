# -*- coding: utf-8 -*-
"""
===================================
Dịch vụ TÀI SẢN KHÁC trong danh mục
===================================

Quản lý tài sản ngoài cổ phiếu: VÀNG, TIẾT KIỆM, TRÁI PHIẾU — theo dõi thủ công
theo GIÁ TRỊ HIỆN TẠI (VND). Mục đích: gộp vào tổng tài sản ròng và vẽ biểu đồ
phân bổ danh mục đa tài sản, không tham gia cơ chế replay giao dịch của cổ phiếu.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from src.storage import DatabaseManager, PortfolioAccount, PortfolioOtherAsset

logger = logging.getLogger(__name__)

# Các lớp tài sản hợp lệ + nhãn tiếng Việt.
ASSET_CLASSES: Dict[str, str] = {
    "vang": "Vàng",
    "tiet_kiem": "Tiết kiệm",
    "trai_phieu": "Trái phiếu",
}


class OtherAssetService:
    """CRUD tài sản khác (vàng/tiết kiệm/trái phiếu) cho một tài khoản danh mục."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()

    # ------------------------------------------------------------------
    @staticmethod
    def _to_dict(row: PortfolioOtherAsset) -> Dict[str, Any]:
        return {
            "id": row.id,
            "account_id": row.account_id,
            "asset_class": row.asset_class,
            "asset_class_label": ASSET_CLASSES.get(row.asset_class, row.asset_class),
            "label": row.label,
            "value": row.value,
            "interest_rate": row.interest_rate,
            "maturity_date": row.maturity_date.isoformat() if row.maturity_date else None,
            "note": row.note,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    @staticmethod
    def _parse_date(value: Optional[str]) -> Optional[date]:
        if not value:
            return None
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d").date()
        except ValueError:
            raise ValueError(f"Ngày không hợp lệ (cần YYYY-MM-DD): {value}")

    def _validate(self, asset_class: str, label: str, value: float) -> None:
        if asset_class not in ASSET_CLASSES:
            raise ValueError(f"Loại tài sản không hợp lệ: {asset_class}")
        if not (label or "").strip():
            raise ValueError("Tên tài sản không được để trống")
        if value is None or float(value) < 0:
            raise ValueError("Giá trị phải là số không âm")

    def _ensure_account(self, session, account_id: int) -> None:
        acc = session.get(PortfolioAccount, account_id)
        if acc is None:
            raise ValueError(f"Không tìm thấy tài khoản: {account_id}")

    # ------------------------------------------------------------------
    def list_assets(self, account_id: int) -> Dict[str, Any]:
        """Danh sách tài sản khác + tổng & cơ cấu theo lớp."""
        with self.db.get_session() as session:
            rows = (
                session.query(PortfolioOtherAsset)
                .filter(PortfolioOtherAsset.account_id == account_id)
                .order_by(PortfolioOtherAsset.asset_class.asc(), PortfolioOtherAsset.id.asc())
                .all()
            )
            items = [self._to_dict(r) for r in rows]

        by_class: Dict[str, float] = {k: 0.0 for k in ASSET_CLASSES}
        for it in items:
            by_class[it["asset_class"]] = by_class.get(it["asset_class"], 0.0) + (it["value"] or 0.0)
        total = round(sum(by_class.values()), 2)
        return {
            "account_id": account_id,
            "items": items,
            "total_value": total,
            "by_class": [
                {"asset_class": k, "label": ASSET_CLASSES[k], "value": round(by_class.get(k, 0.0), 2)}
                for k in ASSET_CLASSES
            ],
        }

    def create_asset(
        self,
        *,
        account_id: int,
        asset_class: str,
        label: str,
        value: float,
        interest_rate: Optional[float] = None,
        maturity_date: Optional[str] = None,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._validate(asset_class, label, value)
        mdate = self._parse_date(maturity_date)
        with self.db.get_session() as session:
            self._ensure_account(session, account_id)
            row = PortfolioOtherAsset(
                account_id=account_id,
                asset_class=asset_class,
                label=label.strip(),
                value=float(value),
                interest_rate=float(interest_rate) if interest_rate is not None else None,
                maturity_date=mdate,
                note=(note or "").strip() or None,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return self._to_dict(row)

    def update_asset(
        self,
        asset_id: int,
        *,
        asset_class: Optional[str] = None,
        label: Optional[str] = None,
        value: Optional[float] = None,
        interest_rate: Optional[float] = None,
        maturity_date: Optional[str] = None,
        note: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        with self.db.get_session() as session:
            row = session.get(PortfolioOtherAsset, asset_id)
            if row is None:
                return None
            new_class = asset_class if asset_class is not None else row.asset_class
            new_label = label if label is not None else row.label
            new_value = value if value is not None else row.value
            self._validate(new_class, new_label, new_value)
            row.asset_class = new_class
            row.label = new_label.strip()
            row.value = float(new_value)
            if interest_rate is not None:
                row.interest_rate = float(interest_rate)
            if maturity_date is not None:
                row.maturity_date = self._parse_date(maturity_date)
            if note is not None:
                row.note = note.strip() or None
            session.commit()
            session.refresh(row)
            return self._to_dict(row)

    def delete_asset(self, asset_id: int) -> bool:
        with self.db.get_session() as session:
            row = session.get(PortfolioOtherAsset, asset_id)
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True
