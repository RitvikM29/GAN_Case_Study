# ===================== IMPORTS =====================
import torch
import torch.nn as nn
import torch.optim as optim
from torchvision import datasets, transforms
import matplotlib.pyplot as plt
import numpy as np

# ===================== DEVICE =====================
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"Using device: {device}")

# ===================== SETTINGS =====================
batch_size = 64
z_dim = 100
lr = 0.0002
epochs = 200
show_interval = 10
target_digit = 7

# ===================== DATA =====================
transform = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize((0.5,), (0.5,))
])

dataset = datasets.MNIST(root='./mnist_data/', train=True, transform=transform, download=True)

# 🔥 FILTER SINGLE DIGIT
indices = (dataset.targets == target_digit).nonzero().squeeze()
subset = torch.utils.data.Subset(dataset, indices)

train_loader = torch.utils.data.DataLoader(subset, batch_size=batch_size, shuffle=True)

mnist_dim = 28 * 28

# ===================== MODELS =====================
class Generator(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(z_dim, 256),
            nn.LeakyReLU(0.2),
            nn.Linear(256, 512),
            nn.LeakyReLU(0.2),
            nn.Linear(512, 1024),
            nn.LeakyReLU(0.2),
            nn.Linear(1024, mnist_dim),
            nn.Tanh()
        )
    def forward(self, x):
        return self.net(x)

class Discriminator(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(mnist_dim, 1024),
            nn.LeakyReLU(0.2),
            nn.Dropout(0.3),
            nn.Linear(1024, 512),
            nn.LeakyReLU(0.2),
            nn.Dropout(0.3),
            nn.Linear(512, 256),
            nn.LeakyReLU(0.2),
            nn.Dropout(0.3),
            nn.Linear(256, 1),
            nn.Sigmoid()
        )
    def forward(self, x):
        return self.net(x)

G = Generator().to(device)
D = Discriminator().to(device)

criterion = nn.BCELoss()
G_opt = optim.Adam(G.parameters(), lr=lr, betas=(0.5, 0.999))
D_opt = optim.Adam(D.parameters(), lr=lr, betas=(0.5, 0.999))

fixed_z = torch.randn(16, z_dim).to(device)

# ===================== HISTORY =====================
G_loss_hist, D_loss_hist = [], []
G_score_hist, D_score_hist = [], []

# ===================== EVALUATION =====================
def evaluate_competition(G, D, dataloader):
    G.eval()
    D.eval()

    real_correct = 0
    fake_correct = 0
    total = 0

    with torch.no_grad():
        for real, _ in dataloader:
            real = real.view(real.size(0), -1).to(device)
            batch_size = real.size(0)

            real_preds = D(real)
            real_correct += (real_preds > 0.5).sum().item()

            z = torch.randn(batch_size, z_dim).to(device)
            fake = G(z)

            fake_preds = D(fake)
            fake_correct += (fake_preds < 0.5).sum().item()

            total += batch_size

    D_real_acc = real_correct / total
    D_fake_acc = fake_correct / total

    D_score = (D_real_acc + D_fake_acc) / 2
    G_score = 1 - D_score

    return D_score, G_score

# ===================== VISUAL =====================
def show_generated(images, preds, epoch):
    images = images.cpu().numpy()

    plt.figure(figsize=(6,6))
    for i in range(16):
        plt.subplot(4,4,i+1)
        plt.imshow(images[i][0], cmap='gray')
        label = "REAL" if preds[i] > 0.5 else "FAKE"
        plt.title(f"{label}\n{preds[i]:.2f}", fontsize=8)
        plt.axis('off')

    plt.suptitle(f"Digit {target_digit} @ Epoch {epoch}")
    plt.tight_layout()
    plt.show()

def plot_combined(G_loss, D_loss, G_score, D_score, epoch):
    epochs_range = np.arange(1, len(G_loss)+1)

    # Normalize loss
    G_norm = []
    D_norm = []
    for g, d in zip(G_loss, D_loss):
        total = g + d + 1e-8
        G_norm.append(g / total)
        D_norm.append(d / total)

    plt.figure(figsize=(12,5))

    # ---------- LOSS ----------
    plt.subplot(1,2,1)
    plt.bar(epochs_range, G_norm, label="Generator")
    plt.bar(epochs_range, D_norm, bottom=G_norm, label="Discriminator")
    plt.axhline(y=0.5, linestyle='--')
    plt.title("Loss-Based Competition")
    plt.xlabel("Epoch")
    plt.ylabel("Normalized Loss")
    plt.legend()

    # ---------- ACCURACY ----------
    plt.subplot(1,2,2)
    plt.bar(epochs_range, G_score, label="Generator")
    plt.bar(epochs_range, D_score, bottom=G_score, label="Discriminator")
    plt.axhline(y=0.5, linestyle='--')
    plt.title("Accuracy-Based Competition")
    plt.xlabel("Epoch")
    plt.ylabel("Score")
    plt.legend()

    plt.tight_layout()
    plt.show()

# ===================== TRAIN =====================
print(f"\n🚀 Starting GAN Training for {epochs} epochs...")
print(f"📊 Training on digit {target_digit}")
print(f"📈 Batch size: {batch_size}, Latent dimension: {z_dim}")
print(f"🔧 Learning rate: {lr}, Device: {device}\n")

for epoch in range(1, epochs+1):
    D_losses, G_losses = [], []

    for real, _ in train_loader:
        real = real.view(real.size(0), -1).to(device)

        real_labels = torch.ones(real.size(0),1).to(device)*0.9
        fake_labels = torch.zeros(real.size(0),1).to(device)

        # D
        z = torch.randn(real.size(0), z_dim).to(device)
        fake = G(z)

        D_loss = criterion(D(real), real_labels) + \
                 criterion(D(fake.detach()), fake_labels)

        D_opt.zero_grad()
        D_loss.backward()
        D_opt.step()

        # G
        z = torch.randn(real.size(0), z_dim).to(device)
        fake = G(z)

        G_loss = criterion(D(fake), real_labels)

        G_opt.zero_grad()
        G_loss.backward()
        G_opt.step()

        D_losses.append(D_loss.item())
        G_losses.append(G_loss.item())

    avg_D = np.mean(D_losses)
    avg_G = np.mean(G_losses)

    D_loss_hist.append(avg_D)
    G_loss_hist.append(avg_G)

    # 🎯 Accuracy-based competition
    D_score, G_score = evaluate_competition(G, D, train_loader)
    D_score_hist.append(D_score)
    G_score_hist.append(G_score)

    print(f"[{epoch:3d}] G_loss:{avg_G:.3f} D_loss:{avg_D:.3f} | G_score:{G_score:.3f} D_score:{D_score:.3f}")

    # ===================== EVERY 10 EPOCHS =====================
    if epoch % show_interval == 0:

        with torch.no_grad():
            fake = G(fixed_z).reshape(-1,1,28,28)
            preds = D(fake.view(16,-1)).cpu().numpy().flatten()
            show_generated(fake, preds, epoch)

        plot_combined(G_loss_hist, D_loss_hist,
                      G_score_hist, D_score_hist,
                      epoch)

print("\n✅ Training completed successfully!")
print(f"📊 Final Generator Score: {G_score_hist[-1]:.3f}")
print(f"📊 Final Discriminator Score: {D_score_hist[-1]:.3f}")

# Save models
torch.save(G.state_dict(), './generator_model.pth')
torch.save(D.state_dict(), './discriminator_model.pth')
print("💾 Models saved to './generator_model.pth' and './discriminator_model.pth'")
