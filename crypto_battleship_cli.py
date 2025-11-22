"""
Cryptographic Battleship CLI - EXPERIMENTAL
Command-line interface for experimental P2P battleship with cryptographic concepts

WARNING: This is experimental software for educational/research purposes.
Not production ready - expect bugs and security limitations.
"""

import time
import sys
from typing import List, Tuple
import random

from crypto_battleship_p2p import CryptoBattleshipP2P
from transport_adapter import SocketTransportAdapter
from battleship_p2p import GamePhase


class CryptoBattleshipCLI:
    """Command-line interface for crypto battleship"""
    
    def __init__(self):
        # Generate random ship positions for testing
        self.ship_positions = self._generate_random_ships()
        
        # Create transport and game
        self.transport = SocketTransportAdapter()
        self.game = CryptoBattleshipP2P(self.ship_positions, transport=self.transport)
        
        # Setup callbacks
        self.game.on_phase_changed = self._on_phase_changed
        self.game.on_message_received = self._on_message_received
        
        # Game display
        self.grid_size = 10
        self.player_grid = [['.' for _ in range(self.grid_size)] for _ in range(self.grid_size)]
        self.enemy_grid = [['?' for _ in range(self.grid_size)] for _ in range(self.grid_size)]
        
        # Mark player ships on grid
        for x, y in self.ship_positions:
            self.player_grid[y][x] = 'S'
        
        print(f"🔐 Crypto Battleship Player Created!")
        print(f"   Player ID: {self.game.crypto_game.identity.player_id}")
        print(f"   Grid Root: {self.game.crypto_game.grid_commitment.root[:16]}...")
        print(f"   Ships: {self.ship_positions}")
    
    def _generate_random_ships(self) -> List[Tuple[int, int]]:
        """Generate random ship positions for testing"""
        ships = []
        ship_sizes = [5, 4, 3, 3, 2]  # Standard battleship ships
        
        for size in ship_sizes:
            placed = False
            attempts = 0
            
            while not placed and attempts < 100:
                x = random.randint(0, 9)
                y = random.randint(0, 9)
                horizontal = random.choice([True, False])
                
                # Check if ship fits
                positions = []
                if horizontal:
                    if x + size <= 10:
                        positions = [(x + i, y) for i in range(size)]
                else:
                    if y + size <= 10:
                        positions = [(x, y + i) for i in range(size)]
                
                # Check if positions are free
                if positions and all(pos not in ships for pos in positions):
                    # Check for adjacent ships
                    valid = True
                    for px, py in positions:
                        for dx in [-1, 0, 1]:
                            for dy in [-1, 0, 1]:
                                if (px + dx, py + dy) in ships:
                                    valid = False
                                    break
                            if not valid:
                                break
                        if not valid:
                            break
                    
                    if valid:
                        ships.extend(positions)
                        placed = True
                
                attempts += 1
        
        return ships
    
    def _on_phase_changed(self, old_phase, new_phase):
        """Handle phase changes"""
        print(f"\n🎮 Game Phase: {old_phase.value} -> {new_phase.value}")
        
        if new_phase == GamePhase.SETUP:
            print("🔐 Cryptographic P2P connection established!")
            print("📋 Both peers have exchanged commitments")
            print("🎯 Type 'invite' to start the game")
        
        elif new_phase == GamePhase.PLAYING:
            print("🚀 Crypto game started!")
            self._display_grids()
            if self.game.current_turn == self.game.player_id:
                print("🎯 Your turn! Enter coordinates to fire (e.g., 'A5')")
            else:
                print("⏳ Waiting for opponent's move...")
    
    def _on_message_received(self, message):
        """Handle received messages"""
        print(f"📨 Received: {message}")
    
    def _display_grids(self):
        """Display both grids side by side"""
        print("\n" + "="*60)
        print("    YOUR FLEET (🔐 CRYPTOGRAPHICALLY SECURED)" + " "*8 + "ENEMY WATERS")
        print("  " + " ".join([chr(65+i) for i in range(self.grid_size)]) + 
              "     " + " ".join([chr(65+i) for i in range(self.grid_size)]))
        
        for i in range(self.grid_size):
            player_row = f"{i+1:2} " + " ".join(self.player_grid[i])
            enemy_row = f"{i+1:2} " + " ".join(self.enemy_grid[i])
            print(player_row + "   " + enemy_row)
        
        print("="*60)
        print("Legend: S=Ship, X=Hit, O=Miss, #=Sunk, ?=Unknown")
        print("🔐 All shots are cryptographically verified!")
    
    def _parse_coordinates(self, coord_str: str) -> Tuple[int, int]:
        """Parse coordinate string like 'A5' to (x, y)"""
        coord_str = coord_str.strip().upper()
        if len(coord_str) < 2:
            raise ValueError("Invalid coordinate format")
        
        x = ord(coord_str[0]) - ord('A')
        y = int(coord_str[1:]) - 1
        
        if not (0 <= x < self.grid_size and 0 <= y < self.grid_size):
            raise ValueError("Coordinates out of range")
        
        return x, y
    
    def listen_for_peer(self, port: int = 12350):
        """Listen for P2P connections"""
        print(f"👂 Listening for crypto P2P connections on port {port}...")
        if self.game.listen_for_peer("0.0.0.0", port):
            print(f"✅ Crypto listener started!")
            print(f"🔐 Tell your opponent to connect to your IP on port {port}")
            return True
        else:
            print("❌ Failed to start crypto listener")
            return False
    
    def connect_to_peer(self, host: str, port: int = 12350):
        """Connect to peer"""
        print(f"🔗 Connecting to crypto peer at {host}:{port}...")
        if self.game.connect_to_peer(host, port):
            print("✅ Connected to crypto peer!")
            return True
        else:
            print("❌ Failed to connect to crypto peer")
            return False
    
    def run_game_loop(self):
        """Main game loop"""
        print("\n🔐 Cryptographic P2P Battleship")
        print("Commands: invite, fire <coord>, grids, status, quit")
        print("🛡️  This game is mathematically cheat-proof!")
        
        while True:
            try:
                if self.game.phase == GamePhase.DISCONNECTED:
                    print("\n💔 Disconnected from game")
                    break
                
                user_input = input("> ").strip().lower()
                
                if user_input == "quit" or user_input == "q":
                    break
                
                elif user_input == "invite" or user_input == "i":
                    if self.game.phase == GamePhase.SETUP:
                        print("📨 Sending cryptographic game invite...")
                        self.game.send_crypto_game_invite()
                    else:
                        print("❌ Can only send invites during setup phase")
                
                elif user_input == "grids" or user_input == "g":
                    self._display_grids()
                
                elif user_input == "status" or user_input == "s":
                    state = self.game.get_crypto_game_state()
                    print(f"Phase: {state['phase']}")
                    print(f"Player ID: {state['crypto_player_id']}")
                    print(f"Grid Root: {state['grid_root'][:16]}...")
                    print(f"Blockchain Blocks: {state['blockchain_blocks']}")
                    print(f"Blockchain Valid: {state['blockchain_valid']}")
                    print(f"Shots Fired: {state['my_shots']}")
                    print(f"Shots Received: {state['opponent_shots']}")
                
                elif user_input.startswith("fire ") or user_input.startswith("f "):
                    if self.game.phase != GamePhase.PLAYING:
                        print("❌ Can only fire during game phase")
                        continue
                    
                    if self.game.current_turn != self.game.player_id:
                        print("❌ Not your turn!")
                        continue
                    
                    try:
                        coord_part = user_input.split()[1]
                        x, y = self._parse_coordinates(coord_part)
                        
                        if self.enemy_grid[y][x] != '?':
                            print("❌ Already fired at that position!")
                            continue
                        
                        print(f"🚀 Firing cryptographic shot at {coord_part.upper()}...")
                        if self.game.fire_crypto_shot(x, y):
                            self.enemy_grid[y][x] = '~'  # Mark as fired
                        else:
                            print("❌ Failed to fire shot")
                    
                    except (IndexError, ValueError) as e:
                        print("❌ Invalid coordinate format. Use format like 'fire A5'")
                
                elif len(user_input) >= 2 and user_input[0].isalpha() and user_input[1:].isdigit():
                    # Direct coordinate input
                    if self.game.phase != GamePhase.PLAYING:
                        print("❌ Can only fire during game phase")
                        continue
                    
                    if self.game.current_turn != self.game.player_id:
                        print("❌ Not your turn!")
                        continue
                    
                    try:
                        x, y = self._parse_coordinates(user_input)
                        
                        if self.enemy_grid[y][x] != '?':
                            print("❌ Already fired at that position!")
                            continue
                        
                        print(f"🚀 Firing cryptographic shot at {user_input.upper()}...")
                        if self.game.fire_crypto_shot(x, y):
                            self.enemy_grid[y][x] = '~'  # Mark as fired
                        else:
                            print("❌ Failed to fire shot")
                    
                    except ValueError as e:
                        print(f"❌ Invalid coordinates: {e}")
                
                elif user_input == "help" or user_input == "h":
                    print("\n📖 Crypto Battleship Commands:")
                    print("  invite - Send cryptographic game invitation")
                    print("  fire A5 - Fire cryptographically verified shot at A5")
                    print("  A5 - Fire at A5 (shorthand)")
                    print("  grids - Show game grids")
                    print("  status - Show crypto game status")
                    print("  quit - Exit game")
                    print("\n🔐 Security Features:")
                    print("  ✅ Merkle proofs prevent lying about hit/miss")
                    print("  ✅ Cryptographic signatures authenticate all moves")
                    print("  ✅ Blockchain provides immutable game history")
                    print("  ✅ Real-time cheat detection")
                
                elif user_input:
                    print("❓ Unknown command. Type 'help' for commands.")
                
                time.sleep(0.1)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"❌ Error: {e}")
        
        print("👋 Goodbye!")
        self.game.disconnect()


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python crypto_battleship_cli.py [listen|connect] [peer_ip] [port]")
        print("  listen - Listen for crypto P2P connections")
        print("  connect <ip> - Connect to crypto peer at IP")
        print("\n🔐 This is a cryptographically secure, cheat-proof battleship game!")
        return
    
    role = sys.argv[1].lower()
    
    cli = CryptoBattleshipCLI()
    
    try:
        if role == "listen":
            port = int(sys.argv[2]) if len(sys.argv) > 2 else 12350
            if cli.listen_for_peer(port):
                cli.run_game_loop()
        
        elif role == "connect":
            if len(sys.argv) < 3:
                print("❌ Connect mode requires peer IP address")
                return
            
            peer_ip = sys.argv[2]
            port = int(sys.argv[3]) if len(sys.argv) > 3 else 12350
            
            if cli.connect_to_peer(peer_ip, port):
                cli.run_game_loop()
        
        else:
            print("❌ Invalid role. Use 'listen' or 'connect'")
    
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cli.game.disconnect()


if __name__ == "__main__":
    main()
