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
        elif pattern == 'vip_center':
            self._generate_vip_center_seats(rows, normal_price, premium_price, vip_price)
        elif pattern == 'aisle':
            self._generate_aisle_seats(rows, normal_price, premium_price, vip_price)
        elif pattern == 'luxury':
            self._generate_luxury_seats(rows, normal_price, premium_price, vip_price)
        
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
        
        db.session.commit()
    
    def _generate_vip_center_seats(self, rows, normal_price, premium_price, vip_price):
        """Generate VIP center layout - center seats are VIP, surrounded by premium"""
        from app.database import db
        from decimal import Decimal
        
        center_start = self.total_columns * 0.3
        center_end = self.total_columns * 0.7
        center_width = center_end - center_start
        
        for row in rows:
            for col in range(1, self.total_columns + 1):
                # Center 40% are VIP
                if center_start <= col < center_end:
                    seat_type = 'vip'
                    price = Decimal(str(vip_price))
                # Seats adjacent to center are premium
                elif abs(col - (center_start + center_end) / 2) <= center_width / 2 + 2:
                    seat_type = 'premium'
                    price = Decimal(str(premium_price))
                # Outer seats are normal
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
    
    def _generate_aisle_seats(self, rows, normal_price, premium_price, vip_price):
        """Generate aisle layout with aisles in middle and premium seats on aisles"""
        from app.database import db
        from decimal import Decimal
        
        # Calculate aisle positions (2 aisles at 1/3 and 2/3 of width)
        aisle1 = int(self.total_columns * 0.33)
        aisle2 = int(self.total_columns * 0.67)
        
        for row in rows:
            for col in range(1, self.total_columns + 1):
                # Skip aisles (no seats)
                if col == aisle1 or col == aisle2:
                    continue
                
                # Seats next to aisles are premium
                if abs(col - aisle1) <= 1 or abs(col - aisle2) <= 1:
                    seat_type = 'premium'
                    price = Decimal(str(premium_price))
                # Back rows are VIP
                elif rows.index(row) >= len(rows) * 0.7:
                    seat_type = 'vip'
                    price = Decimal(str(vip_price))
                # Other seats are normal
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
    
    def _generate_luxury_seats(self, rows, normal_price, premium_price, vip_price):
        """Generate luxury layout with VIP back section and couples seats"""
        from app.database import db
        from decimal import Decimal
        
        for i, row in enumerate(rows):
            # Back 30% are VIP
            if i >= len(rows) * 0.7:
                seat_type = 'vip'
                price = Decimal(str(vip_price))
            # Middle 40% are premium
            elif i >= len(rows) * 0.3:
                seat_type = 'premium'
                price = Decimal(str(premium_price))
            # Front 30% are normal
            else:
                seat_type = 'normal'
                price = Decimal(str(normal_price))
            
            # Create seats with some gaps for luxury feel
            for col in range(1, self.total_columns + 1):
                # Skip some seats in VIP section for luxury feel
                if i >= len(rows) * 0.7 and col % 4 == 0:
                    continue
                
                # Create couples seats in VIP section (pairs with space)
                if i >= len(rows) * 0.7 and col % 2 == 0 and col < self.total_columns:
                    # Skip next seat for couples seating
                    if col + 1 <= self.total_columns:
                        continue
                
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
    booking_seats = db.relationship('BookingSeat', backref='screen_seat', lazy=True, overlaps="seat_bookings,screen_seat")
    
    # Unique constraint for seat within a screen
    __table_args__ = (db.UniqueConstraint('screen_id', 'row', 'column', name='_seat_location_uc'),)
    
    def __repr__(self):
        return f'<Seat {self.row}{self.column}>'
    
    @property
    def seat_number(self):
        """Get formatted seat number (e.g., A1, B2)"""
        return f"{self.row}{self.column}"
    
    def get_price_for_show(self, show):
        """Calculate seat price for a specific show with dynamic pricing"""
        base_price = float(self.price)
        
        # Apply show-specific pricing
        if show.weekend_surcharge and show.show_date.weekday() >= 5:  # Saturday (5) or Sunday (6)
            base_price *= (1 + float(show.weekend_surcharge) / 100)
        
        if show.matinee_discount and show.show_time.hour < 17:  # Before 5 PM
            base_price *= (1 - float(show.matinee_discount) / 100)
        
        # Apply seat type multipliers
        if self.type == 'premium':
            base_price *= 1.5
        elif self.type == 'vip':
            base_price *= 2.0
        
        return round(base_price, 2)


class SeatLock(db.Model):
    """Seat lock model for temporary seat reservation during booking"""
    id = db.Column(db.Integer, primary_key=True)
    seat_id = db.Column(db.Integer, db.ForeignKey('seat.id'), nullable=False)
    show_id = db.Column(db.Integer, db.ForeignKey('show.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lock_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # Relationships
    seat = db.relationship('Seat', backref='locks')
    show = db.relationship('Show', backref='seat_locks')
    user = db.relationship('User', backref='seat_locks')
    
    # Unique constraint to prevent double locking
    __table_args__ = (db.UniqueConstraint('seat_id', 'show_id', 'is_active', name='_active_seat_lock_uc'),)
    
    def __repr__(self):
        return f'<SeatLock {self.seat.seat_number} for Show {self.show_id}>'
    
    @classmethod
    def lock_seat(cls, seat_id, show_id, user_id, lock_minutes=10):
        """Lock a seat for a specific show"""
        from datetime import timedelta
        
        # Check if seat is already locked
        existing_lock = cls.query.filter_by(
            seat_id=seat_id,
            show_id=show_id,
            is_active=True
        ).filter(cls.expires_at > datetime.utcnow()).first()
        
        if existing_lock:
            return False, "Seat is already locked"
        
        # Check if seat is already booked
        from app.bookings.models import BookingSeat, Booking
        booked_seat = db.session.query(BookingSeat).join(Booking).filter(
            BookingSeat.seat_id == seat_id,
            Booking.show_id == show_id,
            Booking.status.in_(['confirmed', 'pending'])
        ).first()
        
        if booked_seat:
            return False, "Seat is already booked"
        
        # Create new lock
        expires_at = datetime.utcnow() + timedelta(minutes=lock_minutes)
        lock = cls(
            seat_id=seat_id,
            show_id=show_id,
            user_id=user_id,
            expires_at=expires_at
        )
        
        db.session.add(lock)
        db.session.commit()
        
        return True, f"Seat locked until {expires_at.strftime('%I:%M %p')}"
    
    @classmethod
    def release_lock(cls, seat_id, show_id, user_id=None):
        """Release a seat lock"""
        query = cls.query.filter_by(
            seat_id=seat_id,
            show_id=show_id,
            is_active=True
        )
        
        if user_id:
            query = query.filter_by(user_id=user_id)
        
        lock = query.first()
        if lock:
            lock.is_active = False
            db.session.commit()
            return True
        
        return False
    
    @classmethod
    def release_expired_locks(cls):
        """Release all expired locks"""
        try:
            # Use a single update query instead of updating individual records
            expired_count = db.session.query(cls).filter(
                cls.is_active == True,
                cls.expires_at < datetime.utcnow()
            ).update({cls.is_active: False}, synchronize_session=False)
            
            db.session.commit()
            return expired_count
        except Exception as e:
            db.session.rollback()
            # If there's an integrity error, try deleting expired locks instead
            try:
                expired_locks = cls.query.filter(
                    cls.is_active == True,
                    cls.expires_at < datetime.utcnow()
                ).all()
                
                for lock in expired_locks:
                    db.session.delete(lock)
                
                db.session.commit()
                return len(expired_locks)
            except Exception as e2:
                db.session.rollback()
                return 0
    
    @classmethod
    def get_locked_seats_for_show(cls, show_id):
        """Get all locked seats for a show"""
        return cls.query.filter_by(
            show_id=show_id,
            is_active=True
        ).filter(cls.expires_at > datetime.utcnow()).all()
    
    @classmethod
    def is_seat_locked(cls, seat_id, show_id):
        """Check if a seat is locked for a show"""
        lock = cls.query.filter_by(
            seat_id=seat_id,
            show_id=show_id,
            is_active=True
        ).filter(cls.expires_at > datetime.utcnow()).first()
        
        return lock is not None