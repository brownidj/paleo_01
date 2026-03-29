import folium


def main():
    # JCU Townsville (approx)
    jcu_lat, jcu_lon = -19.3249, 146.7635

    m = folium.Map(location=[jcu_lat, jcu_lon], zoom_start=14)
    folium.Marker([jcu_lat, jcu_lon], tooltip="JCU", popup="James Cook University").add_to(m)

    m.save("jcu_map.html")
    print("Saved: jcu_map.html")


if __name__ == "__main__":
    main()

