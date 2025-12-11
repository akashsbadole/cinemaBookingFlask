"""
Screens Models
"""
from datetime import datetime

# Import db from database module to avoid circular imports
from app.database import db

class Screen(db.Model):
    """Screen model"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    total_rows = db.Column(db.Integer, nullable=False)
    total_columns = db.Column(db.Integer, nullable=False)
    
    # Relationships
    seats = db.relationship('Seat', backref='screen', lazy=True)
    shows = db.relationship('Show', backref='screen', lazy=True)
    
    def __repr__(self):
        return f'<Screen {self.name}>'
    
    def generate_seats(self, pattern='regular', normal_price=100.00, premium_price=150.00, vip_price=250.00, clear_existing=False):
        """Generate seats for this screen based on the specified pattern"""
        from app.database import db
        
        if clear_existing:
            # Remove existing seats
            for seat in self.seats:
                db.session.delete(seat)
            db.session.commit()
        
        # Generate row labels (A, B, C, ...)
        rows = []
        for i in range(self.total_rows):
            row_label = chr(65 + i)  # A, B, C, ...
            rows.append(row_label)
        
        # Generate seats based on pattern
        if pattern == 'regular':
            self._generate_regular_seats(rows, normal_price)
        elif pattern == 'stadium':
            self._generate_stadium_seats(rows, normal_price, premium_price, vip_price)
        elif pattern == 'mixed':
            self._generate_mixed_seats(rows, normal_price, premium_price, vip_price)
        
        db.session.commit()
    
    def _generate_regular_seats(self, rows, normal_price):
        """Generate regular layout - all seats are normal type"""
        from app.database import db
        from decimal import Decimal
        
        for row in rows:
            for col in range(1, self.total_columns + 1):
                seat = Seat(
                    screen_id=self.id,
                    row=row,
                    column=col,
                    type='normal',
                    price=Decimal(str(normal_price))
                )
                db.session.add(seat)
    
    def _generate_stadium_seats(self, rows, normal_price, premium_price, vip_price):
        """Generate stadium layout - back rows are premium/vip"""
        from app.database import db
        from decimal import Decimal
        
        for i, row in enumerate(rows):
            # Back 25% are VIP
            if i >= len(rows) * 0.75:
                seat_type = 'vip'
                price = Decimal(str(vip_price))
            # 25% before that are premium
            elif i >= len(rows) * 0.5:
                seat_type = 'premium'
                price = Decimal(str(premium_price))
            # Front rows are normal
            else:
                seat_type = 'normal'
                price = Decimal(str(normal_price))
            
            for col in range(1, self.total_columns + 1):
                seat = Seat(
                    screen_id=self.id,
                    row=row,
                    column=col,
                    type=seat_type,
                    price=price
                )
                db.session.add(seat)
    
    def _generate_mixed_seats(self, rows, normal_price, premium_price, vip_price):
        """Generate mixed layout - center seats are premium/vip"""
        from app.database import db
        from decimal import Decimal
        
        center_start = self.total_columns * 0.25
        center_end = self.total_columns * 0.75
        
        for row in rows:
            for col in range(1, self.total_columns + 1):
                # Center seats are premium/vip
                if center_start <= col < center_end:
                    # Middle 50% of center are VIP
                    if col < (center_start + center_end) / 2:
                        seat_type = 'vip'
                        price = Decimal(str(vip_price))
                    else:
                        seat_type = 'premium'
                        price = Decimal(str(premium_price))
                else:
                    seat_type = 'normal'
                    price = Decimal(str(normal_price))
                
                seat = Seat(
                    screen_id=self.id,
                    row=row,
                    column=col,
                    type=seat_type,
                    price=price
                )
                db.session.add(seat)
    
    def apply_custom_layout(self, layout_definition, normal_price=100.00, premium_price=150.00, vip_price=250.00):
        """Apply custom layout definition to seats"""
        from app.database import db
        from decimal import Decimal
        
        # Clear existing seats
        for seat in self.seats:
            db.session.delete(seat)
        db.session.commit()
        
        # Parse layout definition
        lines = layout_definition.strip().split('\n')
        price_map = {
            'N': Decimal(str(normal_price)),
            'P': Decimal(str(premium_price)),
            'V': Decimal(str(vip_price))
        }
        
        for line in lines:
            if ':' not in line:
                continue
            
            row_part, pattern = line.split(':', 1)
            row = row_part.strip().upper()
            
            # Validate row
            if len(row) != 1 or not row.isalpha():
                continue
            
            row_index = ord(row) - ord('A')
            if row_index < 0 or row_index >= self.total_rows:
                continue
            
            # Apply pattern to this row
            for col, char in enumerate(pattern.strip()[:self.total_columns]):
                if char.upper() in price_map:
                    seat_type = {
                        'N': 'normal',
                        'P': 'premium',
                        'V': 'vip'
                    }.get(char.upper(), 'normal')
                    
                    seat = Seat(
                        screen_id=self.id,
                        row=row,
                        column=col + 1,
                        type=seat_type,
                        price=price_map[char.upper()]
                    )
                    db.session.add(seat)
        
        db.session.commit()
    
    def get_seat_count_by_type(self):
        """Get count of seats by type"""
        from app.database import db
        
        normal_count = db.session.query(Seat).filter(
            Seat.screen_id == self.id,
            Seat.type == 'normal'
        ).count()
        
        premium_count = db.session.query(Seat).filter(
            Seat.screen_id == self.id,
            Seat.type == 'premium'
        ).count()
        
        vip_count = db.session.query(Seat).filter(
            Seat.screen_id == self.id,
            Seat.type == 'vip'
        ).count()
        
        return {
            'normal': normal_count,
            'premium': premium_count,
            'vip': vip_count,
            'total': normal_count + premium_count + vip_count
        }
    
    def get_seats_grid(self):
        """Get seats arranged in a grid format for display"""
        grid = {}
        
        for seat in self.seats:
            if seat.row not in grid:
                grid[seat.row] = {}
            grid[seat.row][seat.column] = seat
        
        return grid

class Seat(db.Model):
    """Seat model"""
    id = db.Column(db.Integer, primary_key=True)
    screen_id = db.Column(db.Integer, db.ForeignKey('screen.id'), nullable=False)
    row = db.Column(db.String(2), nullable=False)
    column = db.Column(db.Integer, nullable=False)
    type = db.Column(db.Enum('normal', 'premium', 'vip', name='seat_types'), default='normal', nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    
    # Relationships
    booking_seats = db.relationship('BookingSeat', backref='screen_seat', lazy=True, overlaps="seat_bookings")
    
    # Unique constraint for seat within a screen
    __table_args__ = (db.UniqueConstraint('screen_id', 'row', 'column', name='_seat_location_uc'),)
    
    def __repr__(self):
        return f'<Seat {self.row}{self.column}>'