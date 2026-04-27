"""Tests for difficulty attribute mod adjustments."""
import pytest


def get_adjusted_cs(base_cs: float, mods: str) -> float:
    """Calculate CS with mod adjustments."""
    if not mods:
        return base_cs
    
    mods_upper = mods.upper()
    cs = base_cs
    
    if 'HR' in mods_upper:
        cs = min(10.0, cs * 1.3)
    if 'EZ' in mods_upper:
        cs *= 0.5
    
    return round(max(0.0, min(10.0, cs)), 1)


class TestCSModAdjustments:
    """Test CS (Circle Size) mod adjustments."""
    
    def test_cs_no_mods(self):
        """CS without mods should remain unchanged."""
        assert get_adjusted_cs(5.0, '') == 5.0
        assert get_adjusted_cs(3.5, '') == 3.5
        assert get_adjusted_cs(7.0, '') == 7.0
    
    def test_cs_ez(self):
        """EZ halves CS."""
        assert get_adjusted_cs(2.0, 'EZ') == 1.0
        assert get_adjusted_cs(5.0, 'EZ') == 2.5
        assert get_adjusted_cs(7.0, 'EZ') == 3.5
        assert get_adjusted_cs(10.0, 'EZ') == 5.0
    
    def test_cs_hr(self):
        """HR multiplies CS by 1.3 and caps at 10."""
        assert get_adjusted_cs(2.0, 'HR') == 2.6
        assert get_adjusted_cs(5.0, 'HR') == 6.5
        assert get_adjusted_cs(7.0, 'HR') == 9.1
        assert get_adjusted_cs(7.7, 'HR') == 10.0  # Capped
        assert get_adjusted_cs(8.0, 'HR') == 10.0  # Capped
        assert get_adjusted_cs(10.0, 'HR') == 10.0  # Capped
    
    def test_cs_hr_cap_boundary(self):
        """HR caps at exactly 10.0."""
        # 7.69 * 1.3 = 9.997 -> rounds to 10.0
        assert get_adjusted_cs(7.69, 'HR') == 10.0
        # 7.7 * 1.3 = 10.01 -> capped to 10.0
        assert get_adjusted_cs(7.7, 'HR') == 10.0
    
    def test_cs_sample_values(self):
        """Test sample values from the table."""
        # EZ column
        assert get_adjusted_cs(0.2, 'EZ') == 0.1
        assert get_adjusted_cs(1.0, 'EZ') == 0.5
        assert get_adjusted_cs(3.0, 'EZ') == 1.5
        assert get_adjusted_cs(5.0, 'EZ') == 2.5
        assert get_adjusted_cs(7.0, 'EZ') == 3.5
        assert get_adjusted_cs(10.0, 'EZ') == 5.0
        
        # NM column (no mods)
        assert get_adjusted_cs(2.0, '') == 2.0
        assert get_adjusted_cs(4.0, '') == 4.0
        assert get_adjusted_cs(6.0, '') == 6.0
        assert get_adjusted_cs(8.0, '') == 8.0
        assert get_adjusted_cs(10.0, '') == 10.0
        
        # HR column
        assert get_adjusted_cs(0.2, 'HR') == 0.3  # 0.2 * 1.3 = 0.26 -> 0.3
        assert get_adjusted_cs(1.0, 'HR') == 1.3
        assert get_adjusted_cs(2.0, 'HR') == 2.6
        assert get_adjusted_cs(3.0, 'HR') == 3.9
        assert get_adjusted_cs(4.0, 'HR') == 5.2
        assert get_adjusted_cs(5.0, 'HR') == 6.5
        assert get_adjusted_cs(6.0, 'HR') == 7.8
        assert get_adjusted_cs(7.0, 'HR') == 9.1
        assert get_adjusted_cs(7.7, 'HR') == 10.0  # Capped
        assert get_adjusted_cs(8.0, 'HR') == 10.0  # Capped
        assert get_adjusted_cs(10.0, 'HR') == 10.0  # Capped
    
    def test_cs_dt_no_effect(self):
        """DT should not affect CS."""
        assert get_adjusted_cs(5.0, 'DT') == 5.0
        assert get_adjusted_cs(7.0, 'HDDT') == 7.0
    
    def test_cs_ht_no_effect(self):
        """HT should not affect CS."""
        assert get_adjusted_cs(5.0, 'HT') == 5.0
        assert get_adjusted_cs(7.0, 'EZHT') == 3.5  # Only EZ affects it
